"""Payment adapter interface — V2 §4.6.

The interface is async + JSON-friendly so the W2+ switch to a real
channel is a configuration change, not a refactor.
"""
from __future__ import annotations
from typing import Optional

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentIntent:
    """What the order service hands to the payment adapter."""

    order_id: int
    user_id: int
    amount_cents: int
    currency: str = "USD"
    description: str = ""


@dataclass(frozen=True)
class PaymentResult:
    """Normalized return from every adapter."""

    ok: bool
    channel_txn_id: str
    status: str          # pending / succeeded / failed
    error: Optional[str] = None
    raw: Optional[dict] = None


class PaymentAdapter(ABC):
    @abstractmethod
    async def create(self, intent: PaymentIntent) -> PaymentResult: ...
    @abstractmethod
    async def confirm(self, channel_txn_id: str) -> PaymentResult: ...
    @abstractmethod
    async def query(self, channel_txn_id: str) -> PaymentResult: ...
