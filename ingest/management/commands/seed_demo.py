"""Seed runnable demo data (offline) so the whole pipeline can be exercised."""
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from catalog.models import Match, Sport
from ingest import oddsapi
from picks.models import Pick
from picks.services import make_pick, snapshot_for
from scoring import BetType
from wallet.services import grant


class Command(BaseCommand):
    help = "Seed sports, demo users, open matches, and a finished game with picks."

    def handle(self, *args, **opts):
        if not Sport.objects.exists():
            call_command("loaddata", "sports")
        mlb = Sport.objects.get(pk=1)
        now = timezone.now()

        users = {}
        for name in ("alice", "bob", "carol"):
            u, created = User.objects.get_or_create(
                username=name, defaults={"email": f"{name}@example.com"})
            if created:
                u.set_password("demo12345")
                u.save()
                grant(u, settings.SIGNUP_GRANT)
            users[name] = u

        # OPEN upcoming matches from the bundled sample (times bumped to the future)
        open_matches = []
        for i, ev in enumerate(oddsapi.load_sample()):
            m = oddsapi.map_event(ev)
            defaults = {k: m[k] for k in (
                "home", "away", "over_under", "over_extra", "under_extra",
                "home_rl", "away_rl", "home_rl_extra", "away_rl_extra",
                "home_ml", "away_ml", "line_book")}
            defaults.update(sport=mlb, commence_time=now + timedelta(hours=3 + i),
                            status=Match.Status.OPEN, line_updated_at=now)
            match, _ = Match.objects.update_or_create(
                external_id=m["external_id"], defaults=defaults)
            open_matches.append(match)

        # Demo teams (logos + records) so the game page/modal looks real offline.
        from catalog.models import Team
        demo_teams = {
            "Pittsburgh Pirates": ("PIT", "24-29", "4th in NL Central"),
            "Toronto Blue Jays": ("TOR", "30-22", "2nd in AL East"),
            "Detroit Tigers": ("DET", "28-24", "2nd in AL Central"),
            "Baltimore Orioles": ("BAL", "27-25", "3rd in AL East"),
            "New York Yankees": ("NYY", "33-19", "1st in AL East"),
            "Boston Red Sox": ("BOS", "26-26", "4th in AL East"),
            "Los Angeles Dodgers": ("LAD", "34-18", "1st in NL West"),
            "San Francisco Giants": ("SF", "29-23", "2nd in NL West"),
            "Chicago Cubs": ("CHC", "28-25", "2nd in NL Central"),
            "St. Louis Cardinals": ("STL", "27-26", "3rd in NL Central"),
        }
        teams = {}
        for name, (abbr, rec, standing) in demo_teams.items():
            teams[name], _ = Team.objects.update_or_create(
                sport=mlb, espn_id=abbr.lower(),
                defaults=dict(name=name, abbreviation=abbr, record=rec,
                              standing=standing,
                              logo_url=f"https://a.espncdn.com/i/teamlogos/mlb/500/{abbr.lower()}.png"))

        for user, match, bt, comment in (
            (users["alice"], open_matches[0], BetType.OVER, "Both bats hot lately."),
            (users["bob"], open_matches[0], BetType.HOME_ML, ""),
            (users["carol"], open_matches[1], BetType.AWAY_LINE, "Take the points."),
        ):
            try:
                make_pick(user, match, bt, comment)
            except ValueError:
                pass  # idempotent on re-run

        # A FINAL match to demonstrate settlement, including a PUSH (total lands on 8).
        final, _ = Match.objects.update_or_create(
            external_id="demo-final-chc-stl",
            defaults=dict(
                sport=mlb, home="St. Louis Cardinals", away="Chicago Cubs",
                commence_time=now - timedelta(hours=4), status=Match.Status.FINAL,
                home_score=5, away_score=3,                  # total = 8
                over_under=8, over_extra=-110, under_extra=-110,  # whole 8 -> PUSH
                home_rl=-1.5, away_rl=1.5, home_rl_extra=120, away_rl_extra=-140,
                home_ml=-130, away_ml=110, line_book="DraftKings", line_updated_at=now,
            ),
        )
        for user, bt in (
            (users["alice"], BetType.OVER),       # PUSH
            (users["bob"], BetType.UNDER),         # PUSH
            (users["carol"], BetType.HOME_ML),     # WIN  (home won)
            (users["alice"], BetType.HOME_LINE),   # WIN  (5-1.5=3.5 > 3)
            (users["bob"], BetType.AWAY_ML),       # LOSS
        ):
            lp, odds = snapshot_for(final, bt)
            Pick.objects.get_or_create(
                author=user, match=final, market=BetType(bt).market.value,
                defaults=dict(bet_type=int(bt), line_point=lp, odds_price=odds),
            )

        # a demo contest over the open games
        from contests.models import Contest, ContestGame
        contest, _ = Contest.objects.get_or_create(
            name="Tonight's MLB Slate",
            defaults=dict(sport=mlb, starts_at=now - timedelta(hours=1),
                          ends_at=now + timedelta(hours=12), entry_fee=100,
                          status=Contest.Status.OPEN),
        )
        for m in open_matches[:3]:
            ContestGame.objects.get_or_create(contest=contest, match=m)

        # link every demo match to its teams (logos/records on the game page)
        for match in [*open_matches, final]:
            match.home_team = teams.get(match.home)
            match.away_team = teams.get(match.away)
            match.save(update_fields=["home_team", "away_team"])

        self.stdout.write(self.style.SUCCESS(
            "Seeded demo data.\n"
            "  next: python manage.py settle      # grade the finished game\n"
            "        python manage.py runserver   # visit http://127.0.0.1:8000/"))
