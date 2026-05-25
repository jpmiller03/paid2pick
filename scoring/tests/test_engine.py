"""
Pure unit tests for the scoring engine — no Django needed.

    python -m unittest discover -s scoring

Covers every bet type, favorite/underdog moneylines, and every PUSH case
(the situations the legacy code silently scored as losses).
"""
import unittest

from scoring import BetType, Outcome, accustat, grade


class TestGrade(unittest.TestCase):
    # --- totals -----------------------------------------------------------
    def test_over_win_loss_push(self):
        # total = 9 vs line 8.5 -> over wins, under loses
        self.assertIs(grade(BetType.OVER, 5, 4, 8.5), Outcome.WIN)
        self.assertIs(grade(BetType.UNDER, 5, 4, 8.5), Outcome.LOSS)
        # total = 8 vs line 8.5 -> under wins
        self.assertIs(grade(BetType.UNDER, 4, 4, 8.5), Outcome.WIN)
        self.assertIs(grade(BetType.OVER, 4, 4, 8.5), Outcome.LOSS)

    def test_totals_push_on_exact_landing(self):
        # total = 9 vs whole-number line 9 -> push for BOTH sides
        self.assertIs(grade(BetType.OVER, 5, 4, 9), Outcome.PUSH)
        self.assertIs(grade(BetType.UNDER, 5, 4, 9), Outcome.PUSH)

    # --- spreads / run lines ---------------------------------------------
    def test_home_spread(self):
        # home -1.5: home 5, away 4 -> 5-1.5=3.5 > 4? no -> LOSS
        self.assertIs(grade(BetType.HOME_LINE, 5, 4, -1.5), Outcome.LOSS)
        # home -1.5: home 6, away 4 -> 4.5 > 4 -> WIN
        self.assertIs(grade(BetType.HOME_LINE, 6, 4, -1.5), Outcome.WIN)

    def test_away_spread(self):
        # away +1.5: away 4, home 5 -> 4+1.5=5.5 > 5 -> WIN
        self.assertIs(grade(BetType.AWAY_LINE, 5, 4, 1.5), Outcome.WIN)

    def test_spread_push_on_whole_number(self):
        # home -2 (whole): home 6, away 4 -> 4 == 4 -> PUSH
        self.assertIs(grade(BetType.HOME_LINE, 6, 4, -2), Outcome.PUSH)

    # --- money line -------------------------------------------------------
    def test_moneyline(self):
        self.assertIs(grade(BetType.HOME_ML, 5, 4, None), Outcome.WIN)
        self.assertIs(grade(BetType.AWAY_ML, 5, 4, None), Outcome.LOSS)
        self.assertIs(grade(BetType.AWAY_ML, 4, 7, None), Outcome.WIN)

    def test_moneyline_tie_is_push(self):
        # a tie game (e.g. NFL OT) pushes both sides rather than losing both
        self.assertIs(grade(BetType.HOME_ML, 3, 3, None), Outcome.PUSH)
        self.assertIs(grade(BetType.AWAY_ML, 3, 3, None), Outcome.PUSH)

    def test_unknown_bet_type_raises(self):
        with self.assertRaises(ValueError):
            grade(99, 1, 0, 1.5)


class TestAccustat(unittest.TestCase):
    def test_push_and_pending_score_zero(self):
        self.assertEqual(accustat(BetType.OVER, Outcome.PUSH, -110), 0.0)
        self.assertEqual(accustat(BetType.HOME_ML, Outcome.PENDING, 150), 0.0)

    def test_spread_total_symmetric(self):
        # juice -110 -> base 99; win +99, loss -99
        self.assertAlmostEqual(accustat(BetType.OVER, Outcome.WIN, -110), 99.0)
        self.assertAlmostEqual(accustat(BetType.OVER, Outcome.LOSS, -110), -99.0)
        self.assertAlmostEqual(accustat(BetType.HOME_LINE, Outcome.WIN, -110), 99.0)

    def test_moneyline_favorite(self):
        # favorite -150 win -> 110 - 15 = 95 ; loss -> -150
        self.assertAlmostEqual(accustat(BetType.HOME_ML, Outcome.WIN, -150), 95.0)
        self.assertAlmostEqual(accustat(BetType.HOME_ML, Outcome.LOSS, -150), -150.0)

    def test_moneyline_underdog(self):
        # underdog +135 win -> full +135 ; loss -> -(110 + 13.5) = -123.5
        self.assertAlmostEqual(accustat(BetType.AWAY_ML, Outcome.WIN, 135), 135.0)
        self.assertAlmostEqual(accustat(BetType.AWAY_ML, Outcome.LOSS, 135), -123.5)


if __name__ == "__main__":
    unittest.main()
