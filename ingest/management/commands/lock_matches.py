"""Replaces legacy lock.php — close picks shortly before kickoff."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Match


class Command(BaseCommand):
    help = "Lock OPEN matches starting within LOCK_LEAD_MINUTES."

    def handle(self, *args, **opts):
        cutoff = timezone.now() + timedelta(minutes=settings.LOCK_LEAD_MINUTES)
        n = Match.objects.filter(
            status=Match.Status.OPEN, commence_time__lte=cutoff
        ).update(status=Match.Status.LOCKED)
        self.stdout.write(self.style.SUCCESS(f"locked {n} match(es)"))
