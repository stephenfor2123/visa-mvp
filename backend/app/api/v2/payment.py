"""
/api/v2/payment/* — V2 §4.5 Payment Service (W6-2, Mock-first).

Endpoints:
  - POST /api/v2/payment/create           (JWT) -> {trade_no, code_url, ...}
  - POST /api/v2/payment/notify           (no auth — called by the Mock provider's
                                          auto-notify task after a 1s delay; in V2.1
                                          this is where the real WxPay/Stripe callback
                                          lands, with HMAC signature verification)
  - GET  /api/v2/payment/{order_no}       (JWT) -> status snapshot
  - POST /api/v2/payment/{order_no}/close (JWT) -> flip pending -> closed

DoD (V2 §4.5 + W6-2 spec):
  - Zero credentials required to run end-to-end (no WECHATPAY_* / STRIPE_*
    env vars, no secret keys, no merchant ids).
  - create_order returns 200 + trade_no + code_url shaped like
    `weixin://wxpay/bizpayurl?pr=MOCKxxx` (clearly a mock placeholder).
  - 1s after create, GET /payment/{order_no} returns `status="paid"`
    because `MockPaymentProvider` self-calls `/payment/notify`.
  - pytest ≥ 3 cases pass, end-to-end curl verifies all 4 endpoints.

V2.1 TODO: drop in real channel adapters behind `Settings.payment_channel`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.security import get_current_user
from app.models.order import Order
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.payment import (
    ClosePaymentResponse,
    CreatePaymentRequest,
    CreatePaymentResponse,
    NotifyPaymentRequest,
    NotifyPaymentResponse,
    QueryPaymentResponse,
)
from app.services.payment_provider import (
    OrderPaymentStatus,
    PaymentProvider,
    get_payment_provider,
)
from sqlalchemy import select


router = APIRouter()


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
async def _load_owned_order(
    db: AsyncSession, *, user_id: int, order_no: str
) -> Order:
    """Load the user's own order — mirror OrderService's privacy posture
    so payment endpoints don't leak existence to other users."""
    order = await db.scalar(select(Order).where(Order.order_no == order_no))
    if order is None or order.user_id != user_id:
        # 4001 = order not found (no existence leak across users)
        raise BizException(
            ErrorCode.ORDER_NOT_FOUND,
            message=f"order {order_no} not found",
            data={"order_no": order_no},
        )
    return order


def _status_to_response(s: OrderPaymentStatus) -> QueryPaymentResponse:
    return QueryPaymentResponse(
        order_no=s.order_no,
        trade_no=s.trade_no,
        status=s.status,
        paid_at=s.paid_at,
        amount_cents=s.amount_cents,
        currency=s.currency,
    )


# --------------------------------------------------------------------------- #
# POST /payment/create                                                        #
# --------------------------------------------------------------------------- #
@router.post(
    "/create",
    response_model=ApiResponse[CreatePaymentResponse],
    status_code=201,
    summary="Create a Mock payment order (returns trade_no + code_url)",
)
async def create_payment(
    body: CreatePaymentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[CreatePaymentResponse]:
    """V2 §4.5 — create a (mock) payment order.

    The order must belong to the current user; otherwise we 404 (no
    existence leak — same convention as `/orders/{no}`).

    On success, returns a `CreatePaymentResponse` whose `code_url` is
    a placeholder shaped like WxPay's `weixin://wxpay/bizpayurl?pr=...`
    so the front-end can render a QR-like icon without breaking
    layouts. The Mock provider schedules an auto-notify task that flips
    the order's payment status to `paid` 1s later — verifiable via a
    subsequent `GET /payment/{order_no}`.
    """
    if body.amount_cents <= 0:
        # Belt-and-braces — the Pydantic `gt=0` validator should already
        # have caught this, but we double-check so the error code is
        # explicit (4014) rather than 1001.
        raise BizException(
            ErrorCode.PAYMENT_AMOUNT_INVALID,
            message=f"amount_cents must be > 0, got {body.amount_cents}",
            data={"amount_cents": body.amount_cents},
        )

    # Order must exist AND belong to current user.
    await _load_owned_order(db, user_id=current_user.id, order_no=body.order_no)

    provider: PaymentProvider = get_payment_provider()
    result = await provider.create_order(
        db,
        order_no=body.order_no,
        amount_cents=body.amount_cents,
        desc=body.desc,
        currency=body.currency,
    )

    return ApiResponse[CreatePaymentResponse](
        code="1000",
        message="OK",
        data=CreatePaymentResponse(
            order_no=result.order_no,
            trade_no=result.trade_no,
            code_url=result.code_url,
            prepay_id=result.prepay_id,
            expired_at=result.expired_at,
            amount_cents=body.amount_cents,
            currency=body.currency,
            auto_notify_in_seconds=PaymentProvider.AUTO_NOTIFY_DELAY_SECONDS,
        ),
    )


# --------------------------------------------------------------------------- #
# POST /payment/notify                                                        #
# --------------------------------------------------------------------------- #
@router.post(
    "/notify",
    response_model=ApiResponse[NotifyPaymentResponse],
    summary=(
        "Receive a Mock payment callback (no auth — called by the provider's "
        "own auto-notify task 1s after create; V2.1 will replace with HMAC-signed "
        "WxPay/Stripe webhook)."
    ),
)
async def notify_payment(
    body: NotifyPaymentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[NotifyPaymentResponse]:
    """V2 §4.5 — Mock provider's self-callback.

    This endpoint is intentionally **unauthenticated**:
      - In W6-2 it's called by `PaymentProvider._auto_notify` 1s after
        `create_order` so the order's payment status flips to `paid`
        in-process (no external HTTP roundtrip).
      - In V2.1 it will be the real WxPay/Stripe webhook endpoint, with
        HMAC signature verification (not JWT) because the gateway is
        the caller — not an end user.

    Idempotency: calling twice with the same `order_no` is a no-op
    after the first success — the second call returns 200 with the
    existing `paid_at` (replays are common in real channel flows).
    """
    provider: PaymentProvider = get_payment_provider()
    try:
        ok = await provider.handle_notify(
            db,
            order_no=body.order_no,
            trade_no=body.trade_no,
            payload=body.payload,
        )
    except LookupError:
        # Order doesn't exist (or no `orders` row matches) — surface as
        # 404 / 4012 instead of leaking the underlying LookupError as 500.
        # The gateway could in theory call /notify for an order we never
        # saw; the right answer is "no such order", not an internal error.
        raise BizException(
            ErrorCode.PAYMENT_NOT_FOUND,
            message=f"order_no={body.order_no} not found",
            data={"order_no": body.order_no},
        )

    if not ok:
        # Either the order has no payment record yet (notify before
        # create — shouldn't happen in our flow, but is a sane error
        # to surface) or the order was already paid with a mismatched
        # trade_no. Both map to 404 — we don't want callers to be
        # able to probe arbitrary order_nos for "paid" status.
        raise BizException(
            ErrorCode.PAYMENT_NOT_FOUND,
            message=(
                f"no pending payment for order_no={body.order_no}; "
                "ensure create_payment was called first"
            ),
            data={"order_no": body.order_no},
        )

    # Re-query to get the canonical state for the response.
    status = await provider.query_order(db, order_no=body.order_no)
    if status.trade_no is None or status.paid_at is None:
        # Should be unreachable (handle_notify just succeeded), but the
        # type system needs the None branch handled explicitly.
        raise BizException(
            ErrorCode.SERVER_ERROR,
            message="internal: notify succeeded but query returned empty",
        )
    return ApiResponse[NotifyPaymentResponse](
        code="1000",
        message="OK",
        data=NotifyPaymentResponse(
            order_no=status.order_no,
            trade_no=status.trade_no,
            status=status.status,
            paid_at=status.paid_at,
        ),
    )


# --------------------------------------------------------------------------- #
# GET /payment/{order_no}                                                     #
# --------------------------------------------------------------------------- #
@router.get(
    "/{order_no}",
    response_model=ApiResponse[QueryPaymentResponse],
    summary="Query the current payment status for an order (paid / pending / closed)",
)
async def query_payment(
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[QueryPaymentResponse]:
    order = await _load_owned_order(db, user_id=current_user.id, order_no=order_no)
    provider: PaymentProvider = get_payment_provider()
    status = await provider.query_order(db, order_no=order.order_no)
    if status.status == "none":
        # 404 makes it clear that "no payment record exists yet" is
        # a different state from "pending" / "paid". Front-end uses
        # this to decide whether to show a "Pay now" button.
        raise BizException(
            ErrorCode.PAYMENT_NOT_FOUND,
            message=(
                f"no payment record for order_no={order_no}; "
                "call POST /payment/create first"
            ),
            data={"order_no": order_no},
        )
    return ApiResponse[QueryPaymentResponse](
        code="1000",
        message="OK",
        data=_status_to_response(status),
    )


# --------------------------------------------------------------------------- #
# POST /payment/{order_no}/close                                              #
# --------------------------------------------------------------------------- #
@router.post(
    "/{order_no}/close",
    response_model=ApiResponse[ClosePaymentResponse],
    summary="Close an unpaid order (pending → closed; cannot close paid orders)",
)
async def close_payment(
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ClosePaymentResponse]:
    order = await _load_owned_order(db, user_id=current_user.id, order_no=order_no)
    provider: PaymentProvider = get_payment_provider()
    try:
        status = await provider.close_order(db, order_no=order.order_no)
    except LookupError:
        raise BizException(
            ErrorCode.PAYMENT_NOT_FOUND,
            message=f"no payment record for order_no={order_no}",
            data={"order_no": order_no},
        )
    except ValueError as exc:
        # close_order raises ValueError when the order is already paid.
        # We surface it as a 409 with code PAYMENT_ALREADY_PAID so the
        # front-end can route to a refund flow instead of retrying close.
        raise BizException(
            ErrorCode.PAYMENT_ALREADY_PAID,
            message=str(exc),
            data={"order_no": order_no},
        )
    return ApiResponse[ClosePaymentResponse](
        code="1000",
        message="OK",
        data=ClosePaymentResponse(
            order_no=status.order_no,
            trade_no=status.trade_no,
            status=status.status,
            closed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ),
    )