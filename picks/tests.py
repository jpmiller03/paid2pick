from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from catalog.models import Match, Sport
from scoring import BetType, Outcome
from wallet.services import InsufficientFunds, get_wallet, grant

from .models import Pick, Purchase
from .services import AlreadyPurchased, make_pick, purchase_pick, settle_match


class MarketplaceTests(TestCase):
    def setUp(self):
        self.mlb = Sport.objects.create(category=1, odds_api_key="baseball_mlb",
                                         label="MLB")
        self.seller = User.objects.create_user("seller", password="x")
        self.buyer = User.objects.create_user("buyer", password="x")
        grant(self.buyer, 1000)
        self.match = Match.objects.create(
            sport=self.mlb, external_id="t1", home="Cards", away="Cubs",
            commence_time=timezone.now() + timedelta(hours=3),
            status=Match.Status.OPEN,
            over_under=8.5, over_extra=-105, under_extra=-115,
            home_rl=-1.5, away_rl=1.5, home_rl_extra=120, away_rl_extra=-140,
            home_ml=-130, away_ml=110,
        )
        self.pick = make_pick(self.seller, self.match, BetType.OVER, "hot bats")

    def test_purchase_moves_coins(self):
        purchase_pick(self.buyer, self.pick)
        price = settings.PICK_PRICE
        fee = round(price * settings.PLATFORM_CUT)
        self.assertEqual(get_wallet(self.buyer).balance, 1000 - price)
        self.assertEqual(get_wallet(self.seller).balance, price - fee)
        self.assertTrue(Purchase.objects.filter(
            buyer=self.buyer, pick=self.pick,
            status=Purchase.Status.COMPLETED).exists())

    def test_reveal_rules(self):
        stranger = User.objects.create_user("stranger", password="x")
        self.assertTrue(self.pick.is_revealed_to(self.seller))   # author
        self.assertFalse(self.pick.is_revealed_to(stranger))     # stranger hidden
        purchase_pick(self.buyer, self.pick)
        self.assertTrue(self.pick.is_revealed_to(self.buyer))    # buyer unlocked

    def test_cannot_buy_own_pick(self):
        grant(self.seller, 1000)
        with self.assertRaises(ValueError):
            purchase_pick(self.seller, self.pick)

    def test_duplicate_purchase_blocked(self):
        purchase_pick(self.buyer, self.pick)
        with self.assertRaises(AlreadyPurchased):
            purchase_pick(self.buyer, self.pick)

    def test_insufficient_funds_rolls_back(self):
        broke = User.objects.create_user("broke", password="x")  # 0 balance
        with self.assertRaises(InsufficientFunds):
            purchase_pick(broke, self.pick)
        self.assertEqual(get_wallet(broke).balance, 0)
        self.assertEqual(get_wallet(self.seller).balance, 0)  # seller NOT credited
        self.assertFalse(Purchase.objects.filter(buyer=broke).exists())

    def test_settled_pick_is_public_and_unbuyable(self):
        self.match.home_score, self.match.away_score = 5, 4   # total 9 > 8.5 -> over win
        self.match.status = Match.Status.FINAL
        self.match.save()
        settle_match(self.match)
        self.pick.refresh_from_db()
        self.assertEqual(self.pick.outcome, Outcome.WIN.value)
        self.assertFalse(self.pick.is_buyable)
        self.assertTrue(self.pick.is_revealed_to(
            User.objects.create_user("anyone", password="x")))

    def test_buy_view_redirects_and_unlocks(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(f"/picks/{self.pick.id}/buy/")
        self.assertRedirects(resp, "/purchases/")
        resp = self.client.get("/purchases/")
        self.assertContains(resp, "Over 8.5")  # revealed label on the purchases page
