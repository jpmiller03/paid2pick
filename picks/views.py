from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import PickerStats
from catalog.models import Match
from scoring import Outcome
from wallet.services import InsufficientFunds, get_wallet

from .makepick import makepick_rows
from .models import Pick, Purchase
from .services import AlreadyPurchased, make_pick, purchase_pick

SORT_KEYS = {
    "date": (lambda r: r["pick"].match.commence_time, "Game date"),
    "win": (lambda r: -r["win_pct"], "Win %"),
    "accustat": (lambda r: -r["accustat"], "Accustat"),
}


def browse(request):
    """Buy Picks — hidden picks available to purchase, shoppable by reputation."""
    sort = request.GET.get("sort") if request.GET.get("sort") in SORT_KEYS else "win"

    candidates = (
        Pick.objects
        .filter(outcome=Outcome.PENDING.value,
                match__status=Match.Status.OPEN,
                match__commence_time__gte=timezone.now(),
                author__is_active=True)
        .select_related("author", "match", "match__sport")
    )
    overall = {s.user_id: s for s in PickerStats.objects.filter(sport__isnull=True)}

    rows = []
    for p in candidates:
        if not p.is_buyable:
            continue
        if request.user.is_authenticated and p.author_id == request.user.id:
            continue  # don't offer your own picks back to you
        stats = overall.get(p.author_id)
        rows.append({
            "pick": p,
            "win_pct": stats.win_pct if stats else 0.0,
            "accustat": stats.accustat if stats else 0.0,
            "owned": request.user.is_authenticated and p.is_revealed_to(request.user),
        })
    rows.sort(key=SORT_KEYS[sort][0])

    return render(request, "picks/browse.html", {
        "rows": rows,
        "sort": sort,
        "sorts": {k: v[1] for k, v in SORT_KEYS.items()},
        "price": settings.PICK_PRICE,
        "balance": (get_wallet(request.user).balance
                    if request.user.is_authenticated else None),
    })


@login_required
def buy(request, pk):
    pick = get_object_or_404(Pick, pk=pk)
    if request.method != "POST":
        return redirect("picks_browse")
    try:
        purchase_pick(request.user, pick)
        messages.success(request, f"Unlocked: {pick.label()}")
    except AlreadyPurchased:
        messages.info(request, "You already own that pick.")
    except InsufficientFunds:
        messages.error(request, "Not enough coins for that pick.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("purchases")


@login_required
def pick_make(request):
    """HTMX endpoint: create a pick, return the refreshed make-pick widget."""
    if request.method != "POST":
        return redirect("games")
    match = get_object_or_404(Match, pk=request.POST.get("match_id"))
    try:
        make_pick(request.user, match, int(request.POST.get("bet_type", 0)))
    except (ValueError, TypeError):
        pass  # re-render reflects current state (already picked / game closed)
    return render(request, "picks/_makepick.html",
                  {"match": match, "mp_rows": makepick_rows(request.user, match)})


@login_required
def purchases(request):
    bought = (
        Purchase.objects
        .filter(buyer=request.user, status=Purchase.Status.COMPLETED)
        .select_related("pick", "pick__match", "pick__author")
        .order_by("-created_at")
    )
    return render(request, "picks/purchases.html", {
        "purchases": bought,
        "balance": get_wallet(request.user).balance,
    })
