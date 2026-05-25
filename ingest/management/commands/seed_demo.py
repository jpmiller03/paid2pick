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

        self.stdout.write(self.style.SUCCESS(
            "Seeded demo data.\n"
            "  next: python manage.py settle      # grade the finished game\n"
            "        python manage.py runserver   # visit http://127.0.0.1:8000/"))
