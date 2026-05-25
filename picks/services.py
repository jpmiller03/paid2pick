"""
Pick creation, settlement, and stats recomputation.

Settlement is the heart of Phase 1: it grades each pick against the line it
locked in (fixing the legacy moving-line bug), awards accustat, and rebuilds
the leaderboard aggregates from scratch (as the legacy did — derived, never
hand-incremented).
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import PickerStats, User
from catalog.models import Match
from scoring import BetType, Outcome, accustat, grade
from wallet.models import LedgerEntry
from wallet.services import post

from .models import Pick, Purchase


class AlreadyPurchased(Exception):
    pass


def snapshot_for(match, bet_type):
    """The (line_point, odds_price) a pick locks in, by bet type."""
    bt = BetType(int(bet_type))
    return {
        BetType.OVER: (match.over_under, match.over_extra),
        BetType.UNDER: (match.over_under, match.under_extra),
        BetType.HOME_LINE: (match.home_rl, match.home_rl_extra),
        BetType.AWAY_LINE: (match.away_rl, match.away_rl_extra),
        BetType.HOME_ML: (None, match.home_ml),
        BetType.AWAY_ML: (None, match.away_ml),
    }[bt]


def make_pick(user, match, bet_type, comment=""):
    bt = BetType(int(bet_type))
    if not match.is_pickable:
        raise ValueError("This game is not open for picks.")
    line_point, odds_price = snapshot_for(match, bt)
    if odds_price is None:
        raise ValueError("No line available for that bet type yet.")
    if Pick.objects.filter(author=user, match=match, market=bt.market.value).exists():
        raise ValueError("You already have a pick in this market for this game.")
    return Pick.objects.create(
        author=user,
        match=match,
        bet_type=bt.value,
        line_point=line_point,
        odds_price=odds_price,
        comment=comment,
    )


@transaction.atomic
def settle_match(match):
    """Grade all pending picks on a FINAL match, then refresh affected stats."""
    if match.status != Match.Status.FINAL:
        return 0

    pending = list(match.picks.filter(outcome=Outcome.PENDING.value))
    affected = set()
    for pick in pending:
        outcome = grade(pick.bet_type, match.home_score, match.away_score,
                        pick.line_point)
        pick.outcome = outcome.value
        pick.accustat_points = accustat(pick.bet_type, outcome, pick.odds_price)
        pick.settled_at = timezone.now()
        pick.save(update_fields=["outcome", "accustat_points", "settled_at"])
        affected.add(pick.author_id)
        # Purchases are intentionally NOT refunded on loss/push: the buyer paid
        # for the *prediction* (information), not a wager. This is the legally
        # load-bearing distinction (see MARKETPLACE_SPEC §7.5 / REBUILD_PLAN §6).

    for user in User.objects.filter(pk__in=affected):
        recompute_stats(user)

    match.status = Match.Status.SETTLED
    match.settled_at = timezone.now()
    match.save(update_fields=["status", "settled_at"])
    return len(pending)


def _summarize(picks):
    wins = sum(1 for p in picks if p.outcome == Outcome.WIN.value)
    losses = sum(1 for p in picks if p.outcome == Outcome.LOSS.value)
    decided = wins + losses
    win_pct = (wins / decided * 100) if decided else 0.0
    points = sum(p.accustat_points or 0.0 for p in picks)
    return wins, losses, win_pct, points


def recompute_stats(user):
    """Rebuild PickerStats (overall + per sport) from the user's pick history."""
    settled = list(
        Pick.objects.filter(
            author=user, outcome__in=[Outcome.WIN.value, Outcome.LOSS.value,
                                      Outcome.PUSH.value],
        ).select_related("match", "match__sport")
    )

    # scope None = overall; plus every sport the user has settled picks in
    scopes = {None} | {p.match.sport for p in settled}
    for sport in scopes:
        scoped = settled if sport is None else [p for p in settled
                                                if p.match.sport_id == sport.category]
        wins, losses, win_pct, points = _summarize(scoped)

        decided = [p for p in scoped if p.outcome in
                   (Outcome.WIN.value, Outcome.LOSS.value)]
        decided.sort(key=lambda p: p.settled_at or p.created_at, reverse=True)
        last7 = decided[:7]
        w7, l7, pct7, _ = _summarize(last7)

        PickerStats.objects.update_or_create(
            user=user, sport=sport,
            defaults=dict(
                wins=wins, losses=losses, win_pct=round(win_pct, 1),
                wins_last7=w7, losses_last7=l7, win_pct_last7=round(pct7, 1),
                accustat=round(points, 1),
            ),
        )


@transaction.atomic
def purchase_pick(buyer, pick):
    """
    Reveal a pick to `buyer` for the flat price. Whole thing is one atomic
    transaction: buyer is debited, seller credited their share, platform keeps
    the cut. If the buyer can't afford it, `post()` raises and everything rolls
    back — no stuck-pending purchase (the legacy PayPal two-step bug).
    """
    if pick.author_id == buyer.id:
        raise ValueError("You can't buy your own pick.")
    if not pick.is_buyable:
        raise ValueError("This pick is no longer available.")
    if Purchase.objects.filter(
        buyer=buyer, pick=pick, status=Purchase.Status.COMPLETED
    ).exists():
        raise AlreadyPurchased("You already own this pick.")

    price = settings.PICK_PRICE
    fee = round(price * settings.PLATFORM_CUT)
    seller_share = price - fee

    buy_entry = post(buyer, -price, LedgerEntry.Kind.PICK_PURCHASE, ref=pick)
    sale_entry = post(pick.author, seller_share, LedgerEntry.Kind.PICK_SALE, ref=pick)
    # The `fee` leaves circulation (coin sink). A house wallet could capture it later.

    return Purchase.objects.create(
        buyer=buyer, pick=pick, status=Purchase.Status.COMPLETED,
        price_paid=price, platform_fee=fee,
        buy_entry=buy_entry, sale_entry=sale_entry, completed_at=timezone.now(),
    )
