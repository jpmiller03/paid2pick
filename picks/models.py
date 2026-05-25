from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Match
from scoring import BetType, Market, Outcome

BET_TYPE_CHOICES = [(b.value, b.name.replace("_", " ").title()) for b in BetType]
MARKET_CHOICES = [(m.value, m.name.title()) for m in Market]
OUTCOME_CHOICES = [(o.value, o.name.title()) for o in Outcome]

_MARKET_SHORT = {Market.TOTALS.value: "o/u", Market.SPREAD.value: "line",
                 Market.MONEYLINE.value: "ml"}


def _signed(value):
    v = float(value)
    return f"+{v:g}" if v > 0 else f"{v:g}"


class Pick(models.Model):
    """A prediction on ONE market side. The side is hidden until kickoff or
    purchase (see MARKETPLACE_SPEC.md). Graded against its own snapshot."""
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="picks"
    )
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="picks")
    bet_type = models.PositiveSmallIntegerField(choices=BET_TYPE_CHOICES)
    market = models.CharField(max_length=12, choices=MARKET_CHOICES, editable=False)

    # line snapshot captured at pick time — picks settle against THIS
    line_point = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    odds_price = models.IntegerField()  # american odds at pick time (accustat input)

    comment = models.TextField(blank=True)

    outcome = models.CharField(
        max_length=8, choices=OUTCOME_CHOICES, default=Outcome.PENDING.value
    )
    accustat_points = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["author", "match", "market"],
                name="one_pick_per_market_per_game",
            )
        ]

    def save(self, *args, **kwargs):
        # keep `market` derived from bet_type (also for admin-created picks)
        self.market = BetType(int(self.bet_type)).market.value
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.author} · {self.get_bet_type_display()} · {self.match}"

    # ---- marketplace: reveal + labels ------------------------------------
    @property
    def is_buyable(self):
        """Still hidden and the game hasn't locked → can be purchased."""
        return (self.outcome == Outcome.PENDING.value
                and self.match.locks_at > timezone.now())

    def is_revealed_to(self, user):
        """The core reveal rule (MARKETPLACE_SPEC §2)."""
        if self.outcome != Outcome.PENDING.value:
            return True                              # settled → public
        if timezone.now() >= self.match.locks_at:
            return True                              # kickoff imminent → public
        if getattr(user, "is_authenticated", False):
            if user.id == self.author_id:
                return True                          # your own pick
            if self.purchases.filter(
                buyer=user, status=Purchase.Status.COMPLETED
            ).exists():
                return True                          # you bought it
        return False

    def market_short(self):
        return _MARKET_SHORT[self.market]

    def label(self):
        """Human-readable revealed pick, e.g. 'Over 8.5', '-1.5 Cardinals'."""
        bt = BetType(int(self.bet_type))
        if bt is BetType.OVER:
            return f"Over {self.line_point:g}"
        if bt is BetType.UNDER:
            return f"Under {self.line_point:g}"
        if bt is BetType.HOME_LINE:
            return f"{_signed(self.line_point)} {self.match.home}"
        if bt is BetType.AWAY_LINE:
            return f"{_signed(self.line_point)} {self.match.away}"
        if bt is BetType.HOME_ML:
            return f"{self.match.home} ML"
        return f"{self.match.away} ML"


class Purchase(models.Model):
    """A buyer unlocking a Pick. Replaces the legacy `payments` row; the coin
    transfer is atomic (no more stuck-pending state)."""
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        REFUNDED = "refunded", "Refunded"

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchases"
    )
    pick = models.ForeignKey(Pick, on_delete=models.CASCADE, related_name="purchases")
    status = models.CharField(max_length=10, choices=Status,
                              default=Status.COMPLETED)
    price_paid = models.IntegerField()       # coins
    platform_fee = models.IntegerField(default=0)
    buy_entry = models.ForeignKey(
        "wallet.LedgerEntry", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+"
    )
    sale_entry = models.ForeignKey(
        "wallet.LedgerEntry", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "pick"], name="one_purchase_per_buyer_pick"
            )
        ]

    def __str__(self):
        return f"{self.buyer} bought {self.pick_id}"
