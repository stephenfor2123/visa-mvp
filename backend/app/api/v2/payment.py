"""
/api/v2/payment/* — V2 §4.5 Payment Service (W6-2, Mock-first).

Endpoints:
  - POST /api/v2/payment/create           (JWT) -> {trade_no, code_url, ...}
  - GET  /api/v2/payment/config           (public) -> active channel + publishable key
  - POST /api/v2/payment/notify           (no auth — Mock auto-notify; kept for mock)
  - POST /api/v2/payment/stripe-webhook   (no auth — Stripe signed webhook, Phase A)
  - GET  /api/v2/payment/{order_no}       (JWT) -> status snapshot
  - POST /api/v2/payment/{order_no}/close (JWT) -> flip pending -> closed
  - POST /api/v2/payment/{order_no}/refund (JWT) -> refund paid order

DoD (V2 §4.5 + W6-2 spec):
  - Zero credentials required to run end-to-end (no WECHATPAY_* / STRIPE_*
    env vars, no secret keys, no merchant ids).
  - create_order returns 200 + trade_no + code_url shaped like
    `weixin://wxpay/bizpayurl?pr=MOCKxxx` (clearly a mock placeholder).
  - 1s after create, GET /payment/{order_no} returns `status="paid"`
    because `MockPaymentProvider` self-calls `/payment/notify`.
  - pytest ≥ 3 cases pass, end-to-end curl verifies all 4 endpoints.

# V2.1 TODO: drop in real channel adapters behind `Settings.payment_channel` (done).
# RPA / insurance routers gated by feature flags — see docs/PRODUCT_SCOPE.md.
"""
import json as _json
import time
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal, get_db
from app.core.errors import BizException, ErrorCode
from app.core.metrics import timed
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.order import Order
from app.models.user import User
from app.models.webhook_event import WebhookEvent
from app.schemas.common import ApiResponse
from app.schemas.payment import (
    ClosePaymentResponse,
    CreatePaymentRequest,
    CreatePaymentResponse,
    NotifyPaymentRequest,
    NotifyPaymentResponse,
    PaymentConfigResponse,
    QueryPaymentResponse,
    RefundPaymentRequest,
    RefundPaymentResponse,
)
from app.services.payment_provider import (
    OrderPaymentStatus,
    PaymentProvider,
    get_payment_provider,
)
from sqlalchemy import select


router = APIRouter()
_log = get_logger()


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
    raw = s.raw or {}
    return QueryPaymentResponse(
        order_no=s.order_no,
        trade_no=s.trade_no,
        status=s.status,
        paid_at=s.paid_at,
        amount_cents=s.amount_cents,
        currency=s.currency,
        refunded_at=_parse_iso(raw.get("refunded_at")),
        refund_trade_no=raw.get("refund_trade_no"),
        refund_amount_cents=raw.get("refund_amount_cents"),
    )


def _parse_iso(value: object) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Stripe webhook helpers (W16-3)                                            #
# --------------------------------------------------------------------------- #
def _verify_stripe_signature(
    body: bytes,
    sig_header: str,
    webhook_secret: str,
) -> dict:
    """Verify and parse a Stripe webhook payload.

    Args:
        body: Raw request body bytes (must be the original, unparsed bytes).
        sig_header: Value of the `Stripe-Signature` request header.
        webhook_secret: The `whsec_xxx` signing secret for this endpoint.

    Returns:
        The verified Stripe event dict.

    Raises:
        BizException with PAYMENT_SIGNATURE_INVALID (4001-range) on failure.
        The BizException is raised so FastAPI converts it to an HTTP 400,
        which is what Stripe expects when rejecting a bad signature.
    """
    if not webhook_secret:
        _log.warning(
            "stripe webhook received but STRIPE_WEBHOOK_SECRET is empty; "
            "rejecting (production must set the secret)"
        )
        raise BizException(
            ErrorCode.PAYMENT_SIGNATURE_INVALID,
            message="webhook secret not configured",
        )

    import stripe as _stripe

    try:
        event = _stripe.Webhook.construct_event(
            body, sig_header, webhook_secret
        )
    except _stripe.error.SignatureVerificationError as exc:
        _log.warning(
            "stripe signature verification failed: {}", exc,
        )
        raise BizException(
            ErrorCode.PAYMENT_SIGNATURE_INVALID,
            message=f"invalid stripe signature: {exc}",
        )

    return event  # type: ignore[return-value]


async def _process_stripe_webhook(event: dict) -> None:
    """Background task: process one verified Stripe event.

    This runs AFTER the endpoint has already returned 200 OK to Stripe,
    so we don't block the response. The function:

      1. Idempotency — check `webhook_events` table for the event id.
         If already processed, log and exit (Stripe retry safety).
      2. Resolve `order_no` from `event.data.object.metadata.order_no`.
      3. Call `handle_notify` with the verified payload.
      4. Record the event in `webhook_events` (on success).

    Best-effort errors are swallowed — Stripe retries on 5xx, and we
    already acked with 200 OK.  We log every exception so ops can
    correlate failures in the audit trail.
    """
    from app.services.payment_provider import get_payment_provider

    event_id = event.get("id") or ""
    event_type = event.get("type") or ""
    event_object = (event.get("data") or {}).get("object") or {}
    metadata = event_object.get("metadata") or {}
    order_no = metadata.get("order_no")

    if not order_no:
        _log.info(
            "stripe webhook (bg): no order_no in metadata for "
            "event_id={} type={}; skipping",
            event_id, event_type,
        )
        return

    _log.info(
        "stripe webhook (bg): processing event_id={} type={} order_no={}",
        event_id, event_type, order_no,
    )

    async with AsyncSessionLocal() as db:
        try:
            # ── Idempotency check ───────────────────────────────────────────
            existing = await db.get(WebhookEvent, event_id)
            if existing is not None:
                _log.info(
                    "stripe webhook (bg): event_id={} already processed "
                    "(idempotent replay); skipping",
                    event_id,
                )
                return

            # ── Resolve provider + call handle_notify ───────────────────────
            provider = get_payment_provider()
            ok = await provider.handle_notify(
                db,
                order_no=order_no,
                trade_no=event_object.get("id"),
                payload=event,
            )

            if not ok:
                _log.warning(
                    "stripe webhook (bg): handle_notify returned False "
                    "for order_no={}; will not record event",
                    order_no,
                )
                return

            # ── Record processed event (dedup log) ────────────────────────
            db.add(
                WebhookEvent(
                    event_id=event_id,
                    provider="stripe",
                    event_type=event_type,
                    order_no=order_no,
                    processed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    raw_payload=_json.dumps(event, ensure_ascii=False),
                )
            )
            await db.commit()
            _log.info(
                "stripe webhook (bg): event_id={} processed + recorded "
                "order_no={}",
                event_id, order_no,
            )

        except Exception as exc:
            _log.exception(
                "stripe webhook (bg): failed event_id={} order_no={} err={}",
                event_id, order_no, exc,
            )
            # Do NOT re-raise — we already returned 200 to Stripe.
            # Stripe will retry, and on retry we'll hit the idempotency
            # check above and return 200 immediately.


# --------------------------------------------------------------------------- #
# POST /payment/stripe-webhook  (Phase A — Stripe Test / Live)                #
# --------------------------------------------------------------------------- #
@router.post(
    "/stripe-webhook",
    summary="Stripe webhook receiver (signature-verified, no JWT)",
    status_code=200,
)
@timed
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: Annotated[Optional[str], Header(alias="Stripe-Signature")] = None,
) -> dict:
    """Receive Stripe webhooks for Phase A (test mode) and later live.

    Stripe CLI / Dashboard must point here:
      stripe listen --forward-to localhost:8000/api/v2/payment/stripe-webhook

    Flow:
      1. Read raw body + Stripe-Signature
      2. Verify with STRIPE_WEBHOOK_SECRET → construct_event
      3. Ack 200 immediately, process in background (idempotent)
    """
    raw_body = await request.body()
    if not stripe_signature:
        raise BizException(
            ErrorCode.PAYMENT_SIGNATURE_INVALID,
            message="missing Stripe-Signature header",
        )

    settings = get_settings()
    event = _verify_stripe_signature(
        raw_body,
        stripe_signature,
        settings.stripe_webhook_secret,
    )
    # construct_event may return a Stripe Object — normalise to dict
    if hasattr(event, "to_dict"):
        event_dict = event.to_dict()
    elif isinstance(event, dict):
        event_dict = event
    else:
        event_dict = dict(event)

    background_tasks.add_task(_process_stripe_webhook, event_dict)
    return {"received": True}


# --------------------------------------------------------------------------- #
# POST /payment/create                                                        #
# --------------------------------------------------------------------------- #
@router.post(
    "/create",
    response_model=ApiResponse[CreatePaymentResponse],
    status_code=201,
    summary="Create a payment order (Mock or Stripe PaymentIntent)",
)
@timed
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
    t0 = time.perf_counter()
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

    provider = get_payment_provider()
    try:
        result = await provider.create_order(
            db,
            order_no=body.order_no,
            amount_cents=body.amount_cents,
            desc=body.desc,
            currency=body.currency,
        )
    except ValueError as exc:
        msg = str(exc)
        if "already paid" in msg:
            raise BizException(
                ErrorCode.PAYMENT_ALREADY_PAID,
                message=msg,
                data={"order_no": body.order_no},
            )
        raise BizException(
            ErrorCode.PAYMENT_AMOUNT_INVALID,
            message=msg,
            data={"order_no": body.order_no},
        )
    provider_name = "stripe" if type(provider).__name__ == "StripePaymentProvider" else "mock"
    client_secret = result.prepay_id if provider_name == "stripe" else None
    auto_notify = (
        0.0 if provider_name == "stripe"
        else PaymentProvider.AUTO_NOTIFY_DELAY_SECONDS
    )
    _log.info(
        "payment.create",
        extra={
            "user_id": current_user.id,
            "event_type": "payment.create",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "status": "success",
        },
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
            provider=provider_name,
            client_secret=client_secret,
            auto_notify_in_seconds=auto_notify,
        ),
    )


# --------------------------------------------------------------------------- #
# GET /payment/config                                                         #
# --------------------------------------------------------------------------- #
@router.get(
    "/config",
    response_model=ApiResponse[PaymentConfigResponse],
    summary="Public payment channel config for checkout UI",
)
@timed
async def payment_config() -> ApiResponse[PaymentConfigResponse]:
    """Return the active payment channel and Stripe publishable key (if any)."""
    settings = get_settings()
    channel = settings.payment_channel
    if channel == "stripe" and not settings.stripe_secret_key:
        channel = "mock"
    pk = settings.stripe_publishable_key if channel == "stripe" else None
    return ApiResponse[PaymentConfigResponse](
        code="1000",
        message="OK",
        data=PaymentConfigResponse(
            channel=channel,
            stripe_publishable_key=pk or None,
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
@timed
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
    t0 = time.perf_counter()
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
    _log.info(
        "payment.notify",
        extra={
            "user_id": None,
            "event_type": "payment.notify",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "status": status.status,
        },
    )
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
@timed
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
@timed
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


# --------------------------------------------------------------------------- #
# POST /payment/{order_no}/refund                                             #
# --------------------------------------------------------------------------- #
@router.post(
    "/{order_no}/refund",
    response_model=ApiResponse[RefundPaymentResponse],
    summary="Refund a paid order (mock or Stripe channel)",
)
@timed
async def refund_payment(
    body: RefundPaymentRequest,
    order_no: str = Path(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[RefundPaymentResponse]:
    order = await _load_owned_order(db, user_id=current_user.id, order_no=order_no)
    provider: PaymentProvider = get_payment_provider()
    try:
        status = await provider.refund_order(
            db,
            order_no=order.order_no,
            amount_cents=body.amount_cents,
            reason=body.reason,
        )
    except LookupError:
        raise BizException(
            ErrorCode.PAYMENT_NOT_FOUND,
            message=f"no payment record for order_no={order_no}",
            data={"order_no": order_no},
        )
    except ValueError as exc:
        raise BizException(
            ErrorCode.PAYMENT_AMOUNT_INVALID,
            message=str(exc),
            data={"order_no": order_no},
        )

    raw = status.raw or {}
    refund_trade_no = raw.get("refund_trade_no")
    refunded_at = _parse_iso(raw.get("refunded_at"))
    refund_amount_cents = raw.get("refund_amount_cents")
    if not refund_trade_no or refunded_at is None or refund_amount_cents is None:
        raise BizException(
            ErrorCode.SERVER_ERROR,
            message="internal: refund succeeded but metadata missing",
        )
    return ApiResponse[RefundPaymentResponse](
        code="1000",
        message="OK",
        data=RefundPaymentResponse(
            order_no=status.order_no,
            trade_no=status.trade_no,
            refund_trade_no=refund_trade_no,
            status=status.status,
            refunded_at=refunded_at,
            refund_amount_cents=int(refund_amount_cents),
        ),
    )