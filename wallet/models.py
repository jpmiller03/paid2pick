from django.conf import settings
from django.db import models


class Wallet(models.Model):
    """Per-user balance in integer minor units ("coins"). Never floats."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    balance = models.BigIntegerField(default=0)

    def __str__(self):
        return f"{self.user} — {self.balance} coins"


class LedgerEntry(models.Model):
    """
    Append-only ledger. balance = SUM(amount). This is the seam that makes
    "free now, paid later" additive: real money just adds DEPOSIT/WITHDRAWAL
    kinds + a payment integration — nothing else changes.
    """
    class Kind(models.TextChoices):
        GRANT = "grant", "Signup grant"
        PICK_PURCHASE = "pick_purchase", "Pick purchase"
        PICK_SALE = "pick_sale", "Pick sale"
        CONTEST_ENTRY = "contest_entry", "Contest entry"
        CONTEST_PAYOUT = "contest_payout", "Contest payout"
        REFUND = "refund", "Refund"
        DEPOSIT = "deposit", "Deposit (real money)"        # Phase 4
        WITHDRAWAL = "withdrawal", "Withdrawal (real money)"  # Phase 4

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="entries")
    amount = models.BigIntegerField()  # signed
    kind = models.CharField(max_length=20, choices=Kind)
    ref_type = models.CharField(max_length=40, blank=True)
    ref_id = models.BigIntegerField(null=True, blank=True)
    balance_after = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "ledger entries"

    def __str__(self):
        return f"{self.wallet.user}: {self.amount:+d} ({self.kind})"
