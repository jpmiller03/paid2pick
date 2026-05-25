from django.contrib.auth.models import AbstractUser
from django.db import models

from catalog.models import Sport


class User(AbstractUser):
    """Custom user from day one (cheap now, painful to add later)."""
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.username


class PickerStats(models.Model):
    """
    Materialized leaderboard aggregate, recomputed at settlement. A row per
    (user, sport); the row with sport=NULL is the user's overall line.
    Collapses the legacy 40-column users table (picks_s1..6, streak1..6, ...).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stats")
    sport = models.ForeignKey(
        Sport, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )

    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    win_pct = models.FloatField(default=0.0)

    wins_last7 = models.PositiveIntegerField(default=0)
    losses_last7 = models.PositiveIntegerField(default=0)
    win_pct_last7 = models.FloatField(default=0.0)

    accustat = models.FloatField(default=0.0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "sport"], name="uniq_user_sport_stats"
            )
        ]

    def __str__(self):
        scope = self.sport.label if self.sport_id else "Overall"
        return f"{self.user} — {scope}"
