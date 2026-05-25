from django.conf import settings
from django.db import models
from django.utils import timezone

from catalog.models import Match, Sport
from picks.models import BET_TYPE_CHOICES, MARKET_CHOICES, OUTCOME_CHOICES
from scoring import BetType, Outcome


class Contest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open for entries"
        RUNNING = "running", "Running"
        SETTLED = "settled", "Settled"

    name = models.CharField(max_length=120)
    sport = models.ForeignKey(Sport, on_delete=models.PROTECT, null=True, blank=True,
                              related_name="+")  # null = mixed
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    entry_fee = models.IntegerField(default=0)  # coins; 0 = free
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN)
    games = models.ManyToManyField(Match, through="ContestGame", related_name="contests")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return self.name

    @property
    def is_open(self):
        return self.status == self.Status.OPEN and self.ends_at > timezone.now()

    @property
    def prize_pool(self):
        gross = self.entry_fee * self.entries.count()
        return gross - round(gross * settings.PLATFORM_CUT)


class ContestGame(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE,
                                related_name="contest_games")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["contest", "match"],
                                    name="uniq_contest_match")
        ]


class ContestEntry(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE,
                                related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="contest_entries")
    entry_ledger = models.ForeignKey("wallet.LedgerEntry", on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="+")
    score = models.FloatField(default=0.0)
    rank = models.PositiveIntegerField(null=True, blank=True)
    payout = models.IntegerField(default=0)
    entered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rank", "-score"]
        constraints = [
            models.UniqueConstraint(fields=["contest", "user"],
                                    name="one_entry_per_user_per_contest")
        ]

    def __str__(self):
        return f"{self.user} in {self.contest}"


class ContestPick(models.Model):
    entry = models.ForeignKey(ContestEntry, on_delete=models.CASCADE,
                              related_name="picks")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="+")
    bet_type = models.PositiveSmallIntegerField(choices=BET_TYPE_CHOICES)
    market = models.CharField(max_length=12, choices=MARKET_CHOICES, editable=False)
    line_point = models.DecimalField(max_digits=5, decimal_places=1,
                                     null=True, blank=True)
    odds_price = models.IntegerField()
    outcome = models.CharField(max_length=8, choices=OUTCOME_CHOICES,
                               default=Outcome.PENDING.value)
    accustat_points = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "match", "market"],
                                    name="one_contest_pick_per_market")
        ]

    def save(self, *args, **kwargs):
        self.market = BetType(int(self.bet_type)).market.value
        super().save(*args, **kwargs)
