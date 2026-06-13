"""Payment adapter abstraction (V2 §4.6).

W1 deliverable: interface + Mock adapter that always succeeds.
Real Stripe / Alipay / WxPay land in V2 iteration 2 — drop-in via
`PAYMENT_CHANNEL` env var.
"""
from app.services.payment.adapter import (  # noqa: F401
    PaymentAdapter,
    PaymentIntent,
    PaymentResult,
)
from app.services.payment.factory import get_payment_adapter  # noqa: F401
