from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Sport(models.Model):
    """Replaces the hardcoded category arrays in the legacy odds.php/scores.php."""
    category = models.PositiveSmallIntegerField(primary_key=True)  # 1..6, preserved
    odds_api_key = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=32)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category"]

    def __str__(self):
        return self.label


class Match(models.Model):
    class Status(models.IntegerChoices):
        OPEN = 0, "Open for picks"
        LOCKED = 1, "Locked"
        FINAL = 10, "Final (scored)"
        SETTLED = 20, "Settled"

    sport = models.ForeignKey(Sport, on_delete=models.PROTECT, related_name="matches")
    external_id = models.CharField(max_length=64, unique=True)  # Odds API event id
    home = models.CharField(max_length=80)
    away = models.CharField(max_length=80)
    commence_time = models.DateTimeField(db_index=True)
    status = models.IntegerField(choices=Status, default=Status.OPEN, db_index=True)

    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)

    # current line (latest from the odds feed; snapshotted onto each Pick at pick time)
    over_under = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    over_extra = models.IntegerField(null=True, blank=True)
    under_extra = models.IntegerField(null=True, blank=True)
    home_rl = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    away_rl = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    home_rl_extra = models.IntegerField(null=True, blank=True)
    away_rl_extra = models.IntegerField(null=True, blank=True)
    home_ml = models.IntegerField(null=True, blank=True)
    away_ml = models.IntegerField(null=True, blank=True)
    line_book = models.CharField(max_length=40, blank=True)
    line_updated_at = models.DateTimeField(null=True, blank=True)

    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["commence_time"]
        verbose_name_plural = "matches"

    def __str__(self):
        return f"{self.away} @ {self.home}"

    @property
    def locks_at(self):
        return self.commence_time - timedelta(minutes=settings.LOCK_LEAD_MINUTES)

    @property
    def is_pickable(self):
        return self.status == self.Status.OPEN and self.locks_at > timezone.now()
