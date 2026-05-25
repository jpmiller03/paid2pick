from django.conf import settings
from django.db import models


class Deposit(models.Model):
    """A real-money top-up. When the provider confirms it, we credit the wallet
    with a DEPOSIT ledger entry — the ONLY new thing real money adds. The rest
    of the app (picks, marketplace, contests) is unchanged."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="deposits")
    amount_cents = models.IntegerField()        # what the card was charged
    coins = models.IntegerField()               # what we credit the wallet
    provider = models.CharField(max_length=20, default="fake")
    provider_ref = models.CharField(max_length=120, unique=True)  # e.g. PaymentIntent id
    event_id = models.CharField(max_length=120, blank=True)       # confirming webhook event
    ledger_entry = models.ForeignKey("wallet.LedgerEntry", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="+")
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} +{self.coins} ({self.status})"
