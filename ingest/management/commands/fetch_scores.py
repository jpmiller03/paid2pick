"""Replaces legacy scores.php — pull finals and mark matches FINAL."""
from django.core.management.base import BaseCommand

from catalog.models import Match, Sport
from ingest import oddsapi


class Command(BaseCommand):
    help = "Fetch final scores from The Odds API and mark matches FINAL."

    def handle(self, *args, **opts):
        from django.conf import settings
        if not settings.ODDS_API_KEY:
            self.stdout.write(self.style.WARNING(
                "No ODDS_API_KEY — scores feed unavailable offline. "
                "Use `manage.py seed_demo` for a runnable example."))
            return

        marked = 0
        for sport in Sport.objects.filter(active=True):
            for ev in oddsapi.fetch_scores(sport.odds_api_key):
                sc = oddsapi.map_score(ev)
                if not sc["completed"] or sc["home_score"] is None:
                    continue
                marked += Match.objects.filter(
                    external_id=sc["external_id"]
                ).exclude(status=Match.Status.SETTLED).update(
                    home_score=sc["home_score"],
                    away_score=sc["away_score"],
                    status=Match.Status.FINAL,
                )
        self.stdout.write(self.style.SUCCESS(f"scores: {marked} match(es) FINAL"))
