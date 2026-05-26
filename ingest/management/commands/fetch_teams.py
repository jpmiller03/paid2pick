"""Populate Teams from ESPN (logos + records) and link them to matches.

Logos/identity come from one team-list call per sport. Records/standings come
from per-team detail calls, fetched only for teams that have upcoming games
(bounds the call count — important for college sports with hundreds of teams).
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from catalog.models import Match, Sport, Team
from ingest import espn


def _norm(s):
    return " ".join((s or "").lower().split())


def resolve_match_teams(sport):
    """Link a sport's matches' home/away strings to Team rows by name."""
    teams = list(Team.objects.filter(sport=sport))
    by_name = {_norm(t.name): t for t in teams}
    by_loc = {_norm(t.location): t for t in teams if t.location}
    unlinked = Match.objects.filter(sport=sport).filter(
        Q(home_team__isnull=True) | Q(away_team__isnull=True))
    for m in unlinked:
        for side in ("home", "away"):
            name = _norm(getattr(m, side))
            team = by_name.get(name) or by_loc.get(name) or next(
                (t for t in teams if _norm(t.name).endswith(name)
                 or name.endswith(_norm(t.name))), None)
            if team:
                setattr(m, f"{side}_team", team)
        m.save(update_fields=["home_team", "away_team"])


class Command(BaseCommand):
    help = "Fetch team logos/records from ESPN and link them to matches."

    def handle(self, *args, **opts):
        for sport in Sport.objects.filter(active=True):
            path = espn.SPORT_PATHS.get(sport.category)
            if not path:
                continue
            try:
                listing = espn.team_list(path)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"  {sport.label} teams: {exc}")
                continue
            for t in listing:
                Team.objects.update_or_create(
                    sport=sport, espn_id=t["espn_id"],
                    defaults={k: t[k] for k in
                              ("name", "location", "abbreviation", "logo_url")})
            resolve_match_teams(sport)

            # records: only for teams in upcoming games (bounded)
            upcoming = Match.objects.filter(
                sport=sport, commence_time__gte=timezone.now())
            team_ids = set()
            for m in upcoming.values_list("home_team", "away_team"):
                team_ids.update(i for i in m if i)
            for team in Team.objects.filter(id__in=team_ids):
                try:
                    record, standing = espn.team_detail(path, team.espn_id)
                    team.record, team.standing = record, standing
                    team.save(update_fields=["record", "standing", "updated_at"])
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(f"  {team.name} record: {exc}")

        self.stdout.write(self.style.SUCCESS("teams updated"))
