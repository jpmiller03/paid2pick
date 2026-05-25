from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from accounts.models import PickerStats
from catalog.models import Match
from picks.makepick import makepick_rows


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
    upcoming = (
        Match.objects
        .filter(status__in=[Match.Status.OPEN, Match.Status.LOCKED],
                commence_time__gte=timezone.now())
        .select_related("sport")
        .annotate(n_picks=Count("picks"))
        .order_by("commence_time")
    )

    rows = []
    for m in upcoming:
        show_picker = request.user.is_authenticated and m.is_pickable
        rows.append({
            "match": m,
            "date": timezone.localtime(m.commence_time).strftime("%m/%d %I:%M %p"),
            "away": m.away, "home": m.home,
            "away_rl": _signed(m.away_rl), "away_rl_x": _am(m.away_rl_extra),
            "home_rl": _signed(m.home_rl), "home_rl_x": _am(m.home_rl_extra),
            "away_ml": _am(m.away_ml), "home_ml": _am(m.home_ml),
            "ou": _plain(m.over_under),
            "ou_x": f"{_am(m.over_extra)}/{_am(m.under_extra)}",
            "n_picks": m.n_picks,
            "locked": m.status == Match.Status.LOCKED,
            "mp_rows": makepick_rows(request.user, m) if show_picker else None,
        })

    leaders = (
        PickerStats.objects
        .filter(sport__isnull=True)
        .select_related("user")
        .order_by("-win_pct", "-accustat")[:10]
    )

    return render(request, "web/games.html", {"rows": rows, "leaders": leaders})
