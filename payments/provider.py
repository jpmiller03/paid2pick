"""
Payment provider abstraction. The app talks to this interface, never to Stripe
directly — so the rest of the code is provider-agnostic and testable offline.

  - FakeProvider:  in-process, deterministic. Used in dev/tests; no network.
  - StripeProvider: documented stub. Wire real Stripe here (behind STRIPE_* keys)
    when Phase 4 / the legal gate opens. Nothing else in the app changes.
"""
import json
import secrets

from django.conf import settings


class FakeProvider:
    name = "fake"

    def create_intent(self, deposit):
        return {"ref": "fake_" + secrets.token_hex(8), "client_secret": "fake_secret"}

    def verify_event(self, body, sig_header):
        """In fake mode the webhook body is plain JSON we trust."""
        return json.loads(body or b"{}")


class StripeProvider:
    name = "stripe"

    def create_intent(self, deposit):  # pragma: no cover - Phase 4
        raise NotImplementedError(
            "Phase 4: `pip install stripe`, set STRIPE_SECRET_KEY, and create a "
            "PaymentIntent for deposit.amount_cents; return its id + client_secret."
        )

    def verify_event(self, body, sig_header):  # pragma: no cover - Phase 4
        raise NotImplementedError(
            "Phase 4: verify with stripe.Webhook.construct_event(body, sig_header, "
            "STRIPE_WEBHOOK_SECRET) and map it to {'type','ref','event_id'}."
        )


def get_provider():
    return StripeProvider() if settings.PAYMENTS_PROVIDER == "stripe" else FakeProvider()
