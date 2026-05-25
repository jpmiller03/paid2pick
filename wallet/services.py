"""Wallet operations. Every coin movement goes through `post()` — atomic, and
the single chokepoint where real-money funding will later plug in."""
from django.db import transaction

from .models import LedgerEntry, Wallet


def get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


class InsufficientFunds(Exception):
    pass


@transaction.atomic
def post(user, amount, kind, ref=None, allow_negative=False):
    """Apply a signed `amount` to the user's wallet and append a ledger entry."""
    wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
    new_balance = wallet.balance + amount
    if new_balance < 0 and not allow_negative:
        raise InsufficientFunds(f"{user} has {wallet.balance}, needs {-amount}")

    wallet.balance = new_balance
    wallet.save(update_fields=["balance"])

    return LedgerEntry.objects.create(
        wallet=wallet,
        amount=amount,
        kind=kind,
        ref_type=type(ref).__name__ if ref is not None else "",
        ref_id=getattr(ref, "pk", None),
        balance_after=new_balance,
    )


def grant(user, amount, kind=LedgerEntry.Kind.GRANT):
    return post(user, amount, kind)
