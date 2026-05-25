from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from scoring import BetType
from wallet.services import InsufficientFunds

from .models import Contest, ContestEntry, ContestPick
from .services import AlreadyEntered, enter_contest, make_contest_pick


def contest_list(request):
    contests = Contest.objects.exclude(status=Contest.Status.DRAFT)
    return render(request, "contests/list.html", {"contests": contests})


def contest_detail(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    entry = None
    my_picks = {}
    if request.user.is_authenticated:
        entry = ContestEntry.objects.filter(contest=contest, user=request.user).first()
        if entry:
            my_picks = {(p.match_id, p.market): p for p in entry.picks.all()}

    games = []
    for cg in contest.contest_games.select_related("match"):
        m = cg.match
        options = [
            (BetType.OVER.value, f"Over {m.over_under}" if m.over_under is not None else None),
            (BetType.UNDER.value, f"Under {m.over_under}" if m.over_under is not None else None),
            (BetType.HOME_LINE.value, f"{m.home} {m.home_rl}" if m.home_rl is not None else None),
            (BetType.AWAY_LINE.value, f"{m.away} {m.away_rl}" if m.away_rl is not None else None),
            (BetType.HOME_ML.value, f"{m.home} ML" if m.home_ml is not None else None),
            (BetType.AWAY_ML.value, f"{m.away} ML" if m.away_ml is not None else None),
        ]
        games.append({
            "match": m,
            "options": [(bt, lbl) for bt, lbl in options if lbl],
            "picks_by_market": {mk: my_picks.get((m.id, mk))
                                for mk in ("totals", "spread", "moneyline")},
        })

    standings = contest.entries.select_related("user")
    return render(request, "contests/detail.html", {
        "contest": contest, "entry": entry, "games": games, "standings": standings,
    })


@login_required
def enter(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if request.method == "POST":
        try:
            enter_contest(request.user, contest)
            messages.success(request, "You're in! Make your picks below.")
        except AlreadyEntered:
            messages.info(request, "You already entered this contest.")
        except InsufficientFunds:
            messages.error(request, "Not enough coins for the entry fee.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("contest_detail", pk=pk)


@login_required
def pick(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    entry = get_object_or_404(ContestEntry, contest=contest, user=request.user)
    if request.method == "POST":
        match_id = request.POST.get("match_id")
        bet_type = request.POST.get("bet_type")
        match = get_object_or_404(contest.games, pk=match_id)
        try:
            make_contest_pick(entry, match, int(bet_type))
            messages.success(request, "Pick saved.")
        except (ValueError, KeyError) as exc:
            messages.error(request, str(exc))
    return redirect("contest_detail", pk=pk)
