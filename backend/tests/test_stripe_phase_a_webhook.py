"""Phase A — Stripe webhook route smoke tests (no real Stripe key required)."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_stripe_webhook_rejects_missing_signature(client):
    r = await client.post(
        "/api/v2/payment/stripe-webhook",
        content=b'{"id":"evt_test"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "4015"


@pytest.mark.asyncio
async def test_stripe_webhook_rejects_empty_secret(client):
    r = await client.post(
        "/api/v2/payment/stripe-webhook",
        content=b'{"id":"evt_test"}',
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=1,v1=abc",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "4015"


@pytest.mark.asyncio
async def test_stripe_webhook_accepts_verified_event(client, monkeypatch):
    from app.core import config as config_mod

    settings = config_mod.get_settings()
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_phase_a")

    fake_event = {
        "id": "evt_phase_a_1",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_x", "metadata": {}}},
    }

    with patch(
        "app.api.v2.payment._verify_stripe_signature",
        return_value=fake_event,
    ), patch(
        "app.api.v2.payment._process_stripe_webhook",
    ) as process:
        r = await client.post(
            "/api/v2/payment/stripe-webhook",
            content=b'{"id":"evt_phase_a_1"}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "t=1,v1=ok",
            },
        )
    assert r.status_code == 200
    assert r.json().get("received") is True
    process.assert_called_once()
