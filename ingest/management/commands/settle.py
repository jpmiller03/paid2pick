"""Replaces legacy stats.php/UpdateStats — grade picks and refresh stats."""
from django.core.management.base import BaseCommand

from catalog.models import Match
from picks.services import settle_match


class Command(BaseCommand):
    help = "Settle all FINAL matches: grade picks, award accustat, refresh stats."

    def handle(self, *args, **opts):
        graded = matches = 0
        for match in Match.objects.filter(status=Match.Status.FINAL):
            graded += settle_match(match)
            matches += 1
        self.stdout.write(self.style.SUCCESS(
            f"settled {matches} match(es), graded {graded} pick(s)"))
