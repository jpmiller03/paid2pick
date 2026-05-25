from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from catalog.models import Match, Sport
from scoring import BetType, Outcome
from wallet.services import InsufficientFunds, get_wallet, grant

from .models import Contest, ContestGame, ContestPick
from .services import (AlreadyEntered, enter_contest, make_contest_pick,
                       settle_contest)


class ContestTests(TestCase):
    def setUp(self):
        self.mlb = Sport.objects.create(category=1, odds_api_key="baseball_mlb",
                                         label="MLB")
        now = timezone.now()
        self.match = Match.objects.create(
            sport=self.mlb, external_id="cm1", home="Cards", away="Cubs",
            commence_time=now + timedelta(hours=3), status=Match.Status.OPEN,
            over_under=8.5, over_extra=-110, under_extra=-110,
            home_rl=-1.5, away_rl=1.5, home_rl_extra=120, away_rl_extra=-140,
            home_ml=-130, away_ml=110,
        )
        self.contest = Contest.objects.create(
            name="Friday Night", starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=6), entry_fee=100,
            status=Contest.Status.OPEN)
        ContestGame.objects.create(contest=self.contest, match=self.match)

        self.alice = User.objects.create_user("alice", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        grant(self.alice, 500)
        grant(self.bob, 500)

    def test_entry_charges_fee(self):
        enter_contest(self.alice, self.contest)
        self.assertEqual(get_wallet(self.alice).balance, 400)

    def test_cannot_enter_twice(self):
        enter_contest(self.alice, self.contest)
        with self.assertRaises(AlreadyEntered):
            enter_contest(self.alice, self.contest)

    def test_entry_insufficient_funds_rolls_back(self):
        broke = User.objects.create_user("broke", password="x")
        with self.assertRaises(InsufficientFunds):
            enter_contest(broke, self.contest)
        self.assertEqual(self.contest.entries.count(), 0)

    def test_settle_scores_ranks_and_pays_winner(self):
        ea = enter_contest(self.alice, self.contest)
        eb = enter_contest(self.bob, self.contest)
        # alice takes the home ML (will win); bob takes away ML (will lose)
        make_contest_pick(ea, self.match, BetType.HOME_ML)
        make_contest_pick(eb, self.match, BetType.AWAY_ML)

        # game finishes: home wins 5-3
        self.match.home_score, self.match.away_score = 5, 3
        self.match.status = Match.Status.FINAL
        self.match.save()

        settle_contest(self.contest)
        ea.refresh_from_db(); eb.refresh_from_db()

        self.assertEqual(ea.rank, 1)
        self.assertGreater(ea.score, eb.score)
        # pool = 2*100 - 30% = 200 - 60 = 140 -> winner-take-all
        self.assertEqual(ea.payout, 140)
        self.assertEqual(get_wallet(self.alice).balance, 400 + 140)  # 500-100 entry +140
        self.assertEqual(eb.payout, 0)
        self.contest.refresh_from_db()
        self.assertEqual(self.contest.status, Contest.Status.SETTLED)

    def test_pick_must_be_a_contest_game(self):
        other = Match.objects.create(
            sport=self.mlb, external_id="cm2", home="A", away="B",
            commence_time=timezone.now() + timedelta(hours=3),
            status=Match.Status.OPEN, over_under=8.5, over_extra=-110,
            under_extra=-110, home_ml=-120, away_ml=100)
        e = enter_contest(self.alice, self.contest)
        with self.assertRaises(ValueError):
            make_contest_pick(e, other, BetType.OVER)
