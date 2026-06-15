"""Payment API schemas — V2 §4.5.

Contract:
  - Request/response shapes are flat DTOs; the API layer wraps them in
    `ApiResponse[...]` from `app.schemas.common`.
  - Money is always in minor units (cents) as `int` — never floats.
  - All `*_at` fields are naive UTC (`datetime` without tzinfo) so the
    JSON serialiser outputs `"2026-06-12T08:30:00"` (matches the rest
    of the V2 surface).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# POST /payment/create                                                        #
# --------------------------------------------------------------------------- #
class CreatePaymentRequest(BaseModel):
    order_no: str = Field(
        ..., min_length=1, max_length=32,
        description="V2-YYYYMMDD-NNNNNN order number",
    )
    amount_cents: int = Field(
        ..., gt=0,
        description="Amount in minor units (cents). Must be > 0.",
    )
    currency: str = Field(
        default="USD", min_length=3, max_length=8,
        description="ISO 4217 currency code (USD / EUR / CNY ...)",
    )
    desc: str = Field(
        default="", max_length=256,
        description="Free-form product description (passed to gateway as-is)",
    )


class CreatePaymentResponse(BaseModel):
    order_no: str
    trade_no: str
    code_url: str
    prepay_id: str
    expired_at: datetime
    amount_cents: int
    currency: str
    # Echo the auto-notify contract so the client doesn't have to guess:
    # "1s after this 200 returns, GET /payment/{order_no} will say paid".
    auto_notify_in_seconds: float = 1.0


# --------------------------------------------------------------------------- #
# POST /payment/notify                                                        #
# --------------------------------------------------------------------------- #
class NotifyPaymentRequest(BaseModel):
    order_no: str = Field(..., min_length=1, max_length=32)
    trade_no: Optional[str] = Field(
        default=None,
        description="Optional; included for forward-compat with real channel",
    )
    payload: Optional[dict] = Field(
        default=None,
        description="Optional raw gateway payload (forward-compat)",
    )
    event_id: Optional[str] = Field(
        default=None,
        description="Stripe event.id for deduplication — if set, webhook "
                    "processor checks processed events before executing "
                    "business logic (W16-3 idempotency).",
    )


class NotifyPaymentResponse(BaseModel):
    order_no: str
    trade_no: str
    status: str         # "paid"
    paid_at: datetime


# --------------------------------------------------------------------------- #
# GET /payment/{order_no}                                                     #
# --------------------------------------------------------------------------- #
class QueryPaymentResponse(BaseModel):
    order_no: str
    trade_no: Optional[str]
    status: str         # none | pending | paid | closed | failed
    paid_at: Optional[datetime]
    amount_cents: int
    currency: str


# --------------------------------------------------------------------------- #
# POST /payment/{order_no}/close                                              #
# --------------------------------------------------------------------------- #
class ClosePaymentResponse(BaseModel):
    order_no: str
    trade_no: Optional[str]
    status: str         # "closed"
    closed_at: datetime


__all__ = [
    "CreatePaymentRequest",
    "CreatePaymentResponse",
    "NotifyPaymentRequest",
    "NotifyPaymentResponse",
    "QueryPaymentResponse",
    "ClosePaymentResponse",
]