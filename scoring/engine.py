"""
The scoring engine: grade a pick and award accustat points.

Ported faithfully from the legacy logic in SCORING_SPEC.md, with the three
documented defects fixed:
  - PUSH is a first-class outcome (legacy scored pushes as losses).
  - Grading uses the line the pick LOCKED IN (`line_point`), not the match's
    live, moving line.
  - No copy-paste category bugs (the engine is one small pure function).

Conventions:
  - `line_point` for a SPREAD pick is that side's own signed handicap
    (home -1.5, away +1.5), matching the legacy `home_rl` / `away_rl`.
  - `line_point` for a TOTALS pick is the over/under number.
  - `odds_price` is American odds (e.g. -110, +135) captured at pick time.
"""
from __future__ import annotations

from .enums import BetType, Outcome


def grade(bet_type, home_score: int, away_score: int, line_point) -> Outcome:
    """Return WIN / LOSS / PUSH for one settled pick."""
    bt = BetType(int(bet_type))
    total = home_score + away_score

    if bt is BetType.OVER:
        if total == line_point:
            return Outcome.PUSH
        return Outcome.WIN if total > line_point else Outcome.LOSS

    if bt is BetType.UNDER:
        if total == line_point:
            return Outcome.PUSH
        return Outcome.WIN if total < line_point else Outcome.LOSS

    if bt is BetType.HOME_LINE:
        adjusted = home_score + line_point      # legacy: home_score + home_rl
        if adjusted == away_score:
            return Outcome.PUSH
        return Outcome.WIN if adjusted > away_score else Outcome.LOSS

    if bt is BetType.AWAY_LINE:
        adjusted = away_score + line_point      # legacy: away_score + away_rl
        if adjusted == home_score:
            return Outcome.PUSH
        return Outcome.WIN if adjusted > home_score else Outcome.LOSS

    if bt is BetType.HOME_ML:
        if home_score == away_score:
            return Outcome.PUSH
        return Outcome.WIN if home_score > away_score else Outcome.LOSS

    if bt is BetType.AWAY_ML:
        if home_score == away_score:
            return Outcome.PUSH
        return Outcome.WIN if away_score > home_score else Outcome.LOSS

    raise ValueError(f"unknown bet_type: {bet_type!r}")


def accustat(bet_type, outcome: Outcome, odds_price: int) -> float:
    """
    Signed rating points for a graded pick. Rewards correct longshots, punishes
    missed favorites. PUSH / PENDING score 0. Legacy 110 / 0.1 scale preserved.
    """
    if outcome in (Outcome.PUSH, Outcome.PENDING):
        return 0.0

    bt = BetType(int(bet_type))
    won = outcome is Outcome.WIN
    p = float(odds_price)

    # Spreads & totals settle at the juice attached to the bet.
    if bt.market is not bt.market.MONEYLINE:
        base = 110 - abs(p) * 0.1
        return base if won else -base

    # Money line: favorites (p < 0) vs underdogs (p > 0) are asymmetric.
    if won:
        return (110 - abs(p) * 0.1) if p < 0 else p
    return p if p < 0 else -(110 + abs(p) * 0.1)
