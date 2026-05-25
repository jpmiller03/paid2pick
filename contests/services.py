"""Contest entry, picks, and settlement (scoring + prize payout via the wallet)."""
from django.db import transaction

from scoring import BetType, Outcome, accustat, grade
from wallet.models import LedgerEntry
from wallet.services import post

from .models import Contest, ContestEntry, ContestGame, ContestPick


class AlreadyEntered(Exception):
    pass


def _snapshot(match, bet_type):
    bt = BetType(int(bet_type))
    return {
        BetType.OVER: (match.over_under, match.over_extra),
        BetType.UNDER: (match.over_under, match.under_extra),
        BetType.HOME_LINE: (match.home_rl, match.home_rl_extra),
        BetType.AWAY_LINE: (match.away_rl, match.away_rl_extra),
        BetType.HOME_ML: (None, match.home_ml),
        BetType.AWAY_ML: (None, match.away_ml),
    }[bt]


@transaction.atomic
def enter_contest(user, contest):
    if not contest.is_open:
        raise ValueError("This contest is not open for entries.")
    if ContestEntry.objects.filter(contest=contest, user=user).exists():
        raise AlreadyEntered("You have already entered this contest.")
    ledger = None
    if contest.entry_fee:
        ledger = post(user, -contest.entry_fee,
                      LedgerEntry.Kind.CONTEST_ENTRY, ref=contest)
    return ContestEntry.objects.create(contest=contest, user=user, entry_ledger=ledger)


def make_contest_pick(entry, match, bet_type):
    bt = BetType(int(bet_type))
    if not ContestGame.objects.filter(contest=entry.contest, match=match).exists():
        raise ValueError("That game is not part of this contest.")
    if not match.is_pickable:
        raise ValueError("That game is no longer open.")
    if ContestPick.objects.filter(entry=entry, match=match,
                                  market=bt.market.value).exists():
        raise ValueError("You already picked that market for this game.")
    line_point, odds = _snapshot(match, bt)
    if odds is None:
        raise ValueError("No line available for that bet type.")
    return ContestPick.objects.create(entry=entry, match=match, bet_type=bt.value,
                                      line_point=line_point, odds_price=odds)


@transaction.atomic
def settle_contest(contest):
    """Grade picks, rank entries by total accustat, pay the pool to the top
    (ties split equally). Sets SETTLED so it won't double-pay."""
    if contest.status == Contest.Status.SETTLED:
        return

    # 1. grade every pending contest pick whose game has a final score
    for entry in contest.entries.prefetch_related("picks__match"):
        for p in entry.picks.all():
            m = p.match
            if p.outcome != Outcome.PENDING.value or m.home_score is None:
                continue
            o = grade(p.bet_type, m.home_score, m.away_score, p.line_point)
            p.outcome = o.value
            p.accustat_points = accustat(p.bet_type, o, p.odds_price)
            p.save(update_fields=["outcome", "accustat_points"])

    # 2. score = total accustat; rank by score desc
    entries = list(contest.entries.prefetch_related("picks"))
    for e in entries:
        e.score = round(sum(p.accustat_points or 0.0 for p in e.picks.all()), 1)
    entries.sort(key=lambda e: e.score, reverse=True)

    # 3. winners (ties at top) split the pool
    pool = contest.prize_pool
    top = entries[0].score if entries else None
    winners = [e for e in entries if entries and e.score == top]
    share = (pool // len(winners)) if (winners and pool > 0) else 0

    for i, e in enumerate(entries):
        e.rank = 1 if e in winners else i + 1
        e.payout = 0
        if e in winners and share:
            post(e.user, share, LedgerEntry.Kind.CONTEST_PAYOUT, ref=contest)
            e.payout = share
        e.save(update_fields=["score", "rank", "payout"])

    contest.status = Contest.Status.SETTLED
    contest.save(update_fields=["status"])
