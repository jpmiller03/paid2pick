"""Settle contests whose window has closed (cron)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from contests.models import Contest
from contests.services import settle_contest


class Command(BaseCommand):
    help = "Score and pay out contests past their end time."

    def handle(self, *args, **opts):
        due = Contest.objects.filter(
            ends_at__lt=timezone.now()
        ).exclude(status=Contest.Status.SETTLED)
        n = 0
        for contest in due:
            settle_contest(contest)
            n += 1
        self.stdout.write(self.style.SUCCESS(f"settled {n} contest(s)"))
