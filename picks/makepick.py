"""Shared helper for the HTMX make-a-pick widget (used by the games page and
the pick_make fragment endpoint)."""
from scoring import BetType

from .models import Pick


def makepick_rows(user, match, existing=None):
    """Per-market state: either the user's existing pick, or the two side options.

    Pass `existing` (a {market: Pick} dict, may be empty) to skip the per-match
    query — the games view prefetches every visible match's picks in one query.
    Leave it None (e.g. the single-match HTMX endpoint) to look it up here.
    """
    if existing is None:
        existing = {}
        if getattr(user, "is_authenticated", False):
            existing = {p.market: p
                        for p in Pick.objects.filter(author=user, match=match)}

    groups = [
        ("totals", [
            (BetType.OVER, f"Over {match.over_under:g}" if match.over_under is not None else None),
            (BetType.UNDER, f"Under {match.over_under:g}" if match.over_under is not None else None),
        ]),
        ("spread", [
            (BetType.HOME_LINE, f"{match.home} {match.home_rl:+g}" if match.home_rl is not None else None),
            (BetType.AWAY_LINE, f"{match.away} {match.away_rl:+g}" if match.away_rl is not None else None),
        ]),
        ("moneyline", [
            (BetType.HOME_ML, f"{match.home} ML" if match.home_ml is not None else None),
            (BetType.AWAY_ML, f"{match.away} ML" if match.away_ml is not None else None),
        ]),
    ]

    rows = []
    for market, opts in groups:
        rows.append({
            "market": market,
            "picked": existing.get(market),
            "options": [{"bt": int(bt), "label": lbl} for bt, lbl in opts if lbl],
        })
    return rows
