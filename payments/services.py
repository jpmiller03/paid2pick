from django.conf import settings
from django.db import transaction
from django.utils import timezone

from wallet.models import LedgerEntry
from wallet.services import post

from .models import Deposit
from .provider import get_provider


def create_deposit(user, amount_cents):
    """Open a pending deposit and ask the provider for a payment intent."""
    if amount_cents <= 0:
        raise ValueError("Amount must be positive.")
    coins = amount_cents * settings.COINS_PER_CENT
    provider = get_provider()
    deposit = Deposit.objects.create(
        user=user, amount_cents=amount_cents, coins=coins,
        provider=provider.name, provider_ref=f"tmp_{user.id}_{timezone.now().timestamp()}",
    )
    intent = provider.create_intent(deposit)
    deposit.provider_ref = intent["ref"]
    deposit.save(update_fields=["provider_ref"])
    return deposit, intent


@transaction.atomic
def confirm_deposit(provider_ref, event_id=""):
    """Credit the wallet for a confirmed deposit. Idempotent — a re-delivered
    webhook for the same deposit will not double-credit."""
    deposit = Deposit.objects.select_for_update().get(provider_ref=provider_ref)
    if deposit.status == Deposit.Status.COMPLETED:
        return deposit
    entry = post(deposit.user, deposit.coins, LedgerEntry.Kind.DEPOSIT, ref=deposit)
    deposit.status = Deposit.Status.COMPLETED
    deposit.event_id = event_id
    deposit.ledger_entry = entry
    deposit.completed_at = timezone.now()
    deposit.save(update_fields=["status", "event_id", "ledger_entry", "completed_at"])
    return deposit


@transaction.atomic
def withdraw(user, coins):
    """The mirror of a deposit (Phase 4, behind KYC). Debits the wallet; raises
    InsufficientFunds if short. Real payout to the user happens out-of-band."""
    return post(user, -coins, LedgerEntry.Kind.WITHDRAWAL)
