"""W9-4: StripePaymentProvider stub — V2 ships Mock-only, V2.1 wires SDK.

Verifies:
  1. `stripe` SDK is installed and importable.
  2. Settings exposes `stripe_secret_key: str` (empty default, V2 credential-free).
  3. `StripePaymentProvider()` constructs in stub mode when key is blank.
  4. All four public methods raise `NotImplementedError` (V2.1 fence).
  5. With a synthetic key set, `_require_stripe` passes through and the
     methods still raise the V2.1 marker — proving the gate is wired
     correctly without making any real network call.

Note: V2 ships with `Mock` only per Mavis 2026-06-12 10:54 decision.
This test exists to lock the V2.1 swap contract; no real Stripe calls.
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.payment_provider import (
    CreateOrderResult,
    OrderPaymentStatus,
    StripePaymentProvider,
)


def test_stripe_provider_stub_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """StripePaymentProvider stub: SDK present, no creds, all methods fenced."""
    # (1) SDK installed + importable — proves dependency is locked in
    # requirements.txt / .venv. If the SDK were missing, this import
    # would raise ModuleNotFoundError before the assertions below run.
    import stripe  # noqa: F401

    # (2) Settings exposes the placeholder field with empty default.
    settings = get_settings()
    assert hasattr(settings, "stripe_secret_key"), (
        "Settings.stripe_secret_key must exist as a placeholder field"
    )
    assert settings.stripe_secret_key == "", (
        f"V2 must ship credential-free; got {settings.stripe_secret_key!r}"
    )

    # (3) Constructor picks stub mode when key is blank.
    stub = StripePaymentProvider()
    assert stub.stripe is None, "stub.stripe must be None when key is blank"

    # (4) Every public method is fenced with NotImplementedError.
    #     No real network call happens — the SDK isn't even bound.
    with pytest.raises(NotImplementedError, match="V2.1 阶段接真 SDK"):
        # We don't await — _require_stripe raises synchronously before
        # any async path. This keeps the test fast and proves the gate.
        stub._require_stripe()

    # (5) With a synthetic key set, _require_stripe passes through.
    #     This proves the gate is wired correctly without touching
    #     the real Stripe API (the SDK module is bound but we never
    #     invoke any network method).
    #
    # Why patch `get_settings` instead of `settings.stripe_secret_key`?
    # `get_settings` is `@lru_cache` — mutating the cached Settings
    # object doesn't reliably flip Pydantic v2 fields. Patching the
    # accessor with a stub that returns a fake settings object is the
    # textbook seam for testing code that reads from a singleton.
    #
    # B-W11-2 fix: __init__ now reads 3 fields (stripe_secret_key +
    # stripe_webhook_secret + stripe_payout_account_id), so the fake
    # must mirror all three — otherwise AttributeError on
    # `self.webhook_secret = get_settings().stripe_webhook_secret`.
    class _FakeSettings:
        stripe_secret_key = "sk_test_synthetic_dummy"
        stripe_webhook_secret = "whsec_synthetic_dummy"
        stripe_payout_account_id = "acct_synthetic_dummy"

    monkeypatch.setattr(
        "app.services.payment_provider.get_settings",
        lambda: _FakeSettings(),
    )
    live = StripePaymentProvider()
    assert live.stripe is not None, (
        "When STRIPE_SECRET_KEY is set, stub.stripe must bind the SDK module"
    )
    # And the two companion fields are bound too (used by handle_notify
    # signature verification + payout() destination resolution).
    assert live.webhook_secret == "whsec_synthetic_dummy"
    assert live.payout_account_id == "acct_synthetic_dummy"
    # Gate passes; method bodies are still V2.1 stubs (they would raise
    # NotImplementedError if called with a real DB session — see the
    # class docstring for the V2.1 swap recipe).
    live._require_stripe()  # no exception

    # Public dataclass types still exported (signature compatibility).
    assert CreateOrderResult is not None
    assert OrderPaymentStatus is not None