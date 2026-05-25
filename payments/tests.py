import json

from django.test import TestCase

from accounts.models import User
from wallet.models import LedgerEntry
from wallet.services import InsufficientFunds, get_wallet

from .models import Deposit
from .services import confirm_deposit, create_deposit, withdraw


class PaymentsTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("u", password="x")

    def test_deposit_credits_wallet_with_ledger_entry(self):
        deposit, _ = create_deposit(self.u, 500)   # 500 cents -> 500 coins (1:1)
        self.assertEqual(get_wallet(self.u).balance, 0)  # not yet confirmed
        confirm_deposit(deposit.provider_ref, "evt_1")
        self.assertEqual(get_wallet(self.u).balance, 500)
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, Deposit.Status.COMPLETED)
        self.assertEqual(
            LedgerEntry.objects.filter(
                wallet__user=self.u, kind=LedgerEntry.Kind.DEPOSIT).count(), 1)

    def test_confirm_is_idempotent(self):
        deposit, _ = create_deposit(self.u, 500)
        confirm_deposit(deposit.provider_ref, "evt_1")
        confirm_deposit(deposit.provider_ref, "evt_1")  # webhook re-delivery
        self.assertEqual(get_wallet(self.u).balance, 500)  # NOT 1000
        self.assertEqual(LedgerEntry.objects.filter(
            wallet__user=self.u, kind=LedgerEntry.Kind.DEPOSIT).count(), 1)

    def test_webhook_credits_wallet(self):
        deposit, _ = create_deposit(self.u, 250)
        body = json.dumps({"type": "payment_intent.succeeded",
                           "ref": deposit.provider_ref, "event_id": "e1"})
        resp = self.client.post("/payments/webhook/", data=body,
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(get_wallet(self.u).balance, 250)

    def test_withdraw_debits(self):
        deposit, _ = create_deposit(self.u, 1000)
        confirm_deposit(deposit.provider_ref)
        withdraw(self.u, 400)
        self.assertEqual(get_wallet(self.u).balance, 600)

    def test_withdraw_insufficient_rolls_back(self):
        with self.assertRaises(InsufficientFunds):
            withdraw(self.u, 100)
        self.assertEqual(get_wallet(self.u).balance, 0)
