"""Mock PaymentAdapter — always succeeds, generates fake txn ids.

Real adapters will be added in W2+; this is here so callers can wire
the dependency in W1.
"""
from __future__ import annotations

import secrets
import time

from app.services.payment.adapter import (
    PaymentAdapter,
    PaymentIntent,
    PaymentResult,
)


class MockPaymentAdapter(PaymentAdapter):
    async def create(self, intent: PaymentIntent) -> PaymentResult:
        return PaymentResult(
            ok=True,
            channel_txn_id=f"mock_pay_{int(time.time() * 1000)}_{secrets.token_hex(3)}",
            status="pending",
            raw={"amount_cents": intent.amount_cents, "currency": intent.currency},
        )

    async def confirm(self, channel_txn_id: str) -> PaymentResult:
        return PaymentResult(
            ok=True,
            channel_txn_id=channel_txn_id,
            status="succeeded",
            raw={"note": "mock-confirm always succeeds in W1"},
        )

    async def query(self, channel_txn_id: str) -> PaymentResult:
        return PaymentResult(
            ok=True,
            channel_txn_id=channel_txn_id,
            status="succeeded",
            raw={"note": "mock-query always returns succeeded in W1"},
        )
