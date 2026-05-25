from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .provider import get_provider
from .services import confirm_deposit, create_deposit


@login_required
def add_funds(request):
    if request.method == "POST":
        try:
            amount = int(request.POST.get("amount_cents", "0"))
            deposit, intent = create_deposit(request.user, amount)
        except ValueError as exc:
            messages.error(request, str(exc) or "Enter a valid amount.")
            return redirect("add_funds")

        if get_provider().name == "fake":
            # Offline demo: simulate the provider's success callback immediately.
            confirm_deposit(deposit.provider_ref, event_id="demo")
            messages.success(request, f"Added {deposit.coins} coins.")
        else:  # pragma: no cover - Phase 4
            messages.info(request, "Stripe checkout would open here (Phase 4).")
        return redirect("add_funds")

    return render(request, "payments/add_funds.html", {"provider": get_provider().name})


@csrf_exempt
def webhook(request):
    """Provider success callback → credit the wallet (idempotent)."""
    provider = get_provider()
    event = provider.verify_event(request.body, request.headers.get("Stripe-Signature", ""))
    if event.get("type") == "payment_intent.succeeded" and event.get("ref"):
        confirm_deposit(event["ref"], event.get("event_id", ""))
    return JsonResponse({"received": True})
