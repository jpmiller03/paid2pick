"""Replaces legacy odds.php — pull lines and upsert matches (no team mapping)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Match, Sport
from ingest import oddsapi

LINE_FIELDS = ("home", "away", "commence_time", "over_under", "over_extra",
               "under_extra", "home_rl", "away_rl", "home_rl_extra",
               "away_rl_extra", "home_ml", "away_ml", "line_book")


class Command(BaseCommand):
    help = "Fetch odds from The Odds API (or bundled sample) and upsert matches."

    def handle(self, *args, **opts):
        created = updated = 0
        for sport in Sport.objects.filter(active=True):
            try:
                events = oddsapi.fetch_odds(sport.odds_api_key)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"  {sport.label}: {exc}")
                continue
            for ev in events:
                m = oddsapi.map_event(ev)
                if m["sport_key"] != sport.odds_api_key:
                    continue  # offline sample is all-MLB; skip non-matching sports
                defaults = {k: m[k] for k in LINE_FIELDS}
                defaults["sport"] = sport
                defaults["line_updated_at"] = timezone.now()
                _, was_created = Match.objects.update_or_create(
                    external_id=m["external_id"], defaults=defaults
                )
                created += was_created
                updated += not was_created
        self.stdout.write(self.style.SUCCESS(
            f"odds: {created} new, {updated} updated"))
