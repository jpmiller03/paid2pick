from django.conf import settings
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from accounts.models import PickerStats
from catalog.models import Match, Sport
from picks.makepick import makepick_rows
from picks.models import Pick


def _am(price):
    """American odds with sign."""
    if price is None:
        return "—"
    return f"+{price}" if price > 0 else str(price)


def _signed(point):
    if point is None:
        return "—"
    point = float(point)
    return f"+{point:g}" if point > 0 else f"{point:g}"


def _plain(point):
    return "—" if point is None else f"{float(point):g}"


def games(request):
    base = (
        Match.objects
        .filter(status__in=[Match.Status.OPEN, Match.Status.LOCKED],
                commence_time__gte=timezone.now())
    )

    # Sport filter chips — only sports that actually have upcoming games.
    present = base.values_list("sport__category", flat=True).distinct()
    sport_chips = list(Sport.objects.filter(category__in=present).order_by("category"))
    sel = request.GET.get("sport")
    selected_sport = int(sel) if sel and sel.isdigit() else None

    upcoming = base.select_related("sport").annotate(n_picks=Count("picks"))
    if selected_sport:
        upcoming = upcoming.filter(sport__category=selected_sport)
    upcoming = list(upcoming.order_by("commence_time"))

    # Prefetch this user's picks for every visible game in ONE query (was N+1:
    # the make-a-pick widget previously queried once per game).
    my_picks = {}
    if request.user.is_authenticated:
        from picks.models import Pick
        for p in Pick.objects.filter(author=request.user,
                                     match__in=[m for m in upcoming if m.is_pickable]):
            my_picks.setdefault(p.match_id, {})[p.market] = p

    rows = []
    prev_day = None
    for m in upcoming:
        local = timezone.localtime(m.commence_time)
        day = local.date()
        date_header = local.strftime("%A, %b ") + str(local.day) if day != prev_day else None
        prev_day = day
        show_picker = request.user.is_authenticated and m.is_pickable
        mp = makepick_rows(request.user, m, my_picks.get(m.id, {})) if show_picker else None
        rows.append({
            "match": m,
            "date_header": date_header,                       # set on first game of a new day
            "time": local.strftime("%I:%M %p").lstrip("0"),
            "away": m.away, "home": m.home,
            "away_rl": _signed(m.away_rl), "away_rl_x": _am(m.away_rl_extra),
            "home_rl": _signed(m.home_rl), "home_rl_x": _am(m.home_rl_extra),
            "away_ml": _am(m.away_ml), "home_ml": _am(m.home_ml),
            "ou": _plain(m.over_under),
            "ou_x": f"{_am(m.over_extra)}/{_am(m.under_extra)}",
            "n_picks": m.n_picks,
            "locked": m.status == Match.Status.LOCKED,
            "mp_rows": mp,
            "mp_open": any(not r["picked"] for r in mp) if mp else False,
        })

    leaders = (
        PickerStats.objects
        .filter(sport__isnull=True)
        .select_related("user")
        .order_by("-win_pct", "-accustat")[:10]
    )

    return render(request, "web/games.html", {
        "rows": rows, "leaders": leaders,
        "sport_chips": sport_chips, "selected_sport": selected_sport,
    })


def game_detail(request, pk):
    """Game page with team logos/records, lines, and the picks on it. Renders a
    modal fragment for HTMX requests, the full page otherwise."""
    m = get_object_or_404(
        Match.objects.select_related("sport", "home_team", "away_team"), pk=pk)

    overall = {s.user_id: s for s in PickerStats.objects.filter(sport__isnull=True)}
    picks = []
    for p in Pick.objects.filter(match=m).select_related("author").order_by("-created_at"):
        stats = overall.get(p.author_id)
        picks.append({
            "pick": p,
            "revealed": p.is_revealed_to(request.user),
            "buyable": p.is_buyable,
            "win_pct": stats.win_pct if stats else 0.0,
        })

    show_picker = request.user.is_authenticated and m.is_pickable
    mp = makepick_rows(request.user, m) if show_picker else None
    ctx = {
        "m": m,
        "final": m.status >= Match.Status.FINAL,
        "lines": {
            "ou": _plain(m.over_under),
            "ou_x": f"{_am(m.over_extra)}/{_am(m.under_extra)}",
            "away_rl": _signed(m.away_rl), "away_rl_x": _am(m.away_rl_extra),
            "home_rl": _signed(m.home_rl), "home_rl_x": _am(m.home_rl_extra),
            "away_ml": _am(m.away_ml), "home_ml": _am(m.home_ml),
        },
        "picks": picks,
        "price": settings.PICK_PRICE,
        "mp_rows": mp,
        "mp_open": any(not r["picked"] for r in mp) if mp else False,
    }
    template = ("web/_game_modal.html" if request.headers.get("HX-Request")
                else "web/game_detail.html")
    return render(request, template, ctx)
