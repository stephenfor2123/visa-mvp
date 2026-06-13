"""Payment adapter factory."""
from __future__ import annotations

from functools import lru_cache

from app.services.payment.adapter import PaymentAdapter
from app.services.payment.mock import MockPaymentAdapter


@lru_cache(maxsize=1)
def get_payment_adapter() -> PaymentAdapter:
    """W1 only ships a Mock adapter; extend once Stripe/Alipay land."""
    return MockPaymentAdapter()
