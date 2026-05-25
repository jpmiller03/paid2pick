from wallet.services import get_wallet


def wallet_balance(request):
    """Expose the signed-in user's coin balance to every template (the nav)."""
    if request.user.is_authenticated:
        return {"coins": get_wallet(request.user).balance}
    return {"coins": None}
