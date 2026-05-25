from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import get_object_or_404, redirect, render

from wallet.services import grant

from .models import PickerStats, User


class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)


def register(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            grant(user, settings.SIGNUP_GRANT)  # welcome coins
            login(request, user)
            return redirect("games")
    else:
        form = SignupForm()
    return render(request, "registration/register.html", {"form": form})


def profile(request, pk):
    """Public picker profile: stats + their picks (paywalled until revealed)."""
    from picks.models import Pick  # local import avoids any import-order surprises

    picker = get_object_or_404(User, pk=pk, is_active=True)
    stats = list(PickerStats.objects.filter(user=picker).select_related("sport"))
    overall = next((s for s in stats if s.sport_id is None), None)
    by_sport = sorted((s for s in stats if s.sport_id is not None),
                      key=lambda s: s.sport_id)
    recent = (Pick.objects.filter(author=picker)
              .select_related("match", "match__sport").order_by("-created_at")[:20])
    picks = [{"pick": p, "revealed": p.is_revealed_to(request.user),
              "buyable": p.is_buyable} for p in recent]
    return render(request, "accounts/profile.html", {
        "picker": picker, "overall": overall, "by_sport": by_sport,
        "picks": picks, "price": settings.PICK_PRICE,
    })
