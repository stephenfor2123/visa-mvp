"""Payment provider facade — V2 §4.5 (Payment Service) — W6-2 Mock-first.

This module sits one layer above the lower-level `app.services.payment`
adapter ABC (created in W1). The adapter layer is intentionally a thin
channel-agnostic shim; this facade adds:

  1. **Order-coupled state** — `create_order` takes an internal
     `order_no` (the V2-YYYYMMDD-NNNNNN string), and `query_order`
     returns a payment status the API layer can hand straight to the
     front-end.
  2. **Auto-notify simulation** — 1s after `create_order`, the
     provider self-calls `handle_notify` so the order's payment
     status transitions `pending → paid` exactly like a real WxPay
     callback would land (W6-2 spec: "1s 后自动 POST 自己").
  3. **Persist payment metadata to `orders.extra` JSON** — we store
     `{trade_no, status, paid_at, ...}` on the existing Order row,
     so a subsequent `GET /api/v2/orders/{no}` can show "已支付"
     without a new alembic migration. The order state machine
     (`created / submitted / ...`) is intentionally NOT mutated —
     "已支付" is a payment-level signal, not an order lifecycle
     state in V2 §4.2.4.
  4. **Zero credentials** — fully mock, no WECHATPAY_*/STRIPE_*
     config required. Real-channel switch lives behind a TODO marker
     at the bottom of this file for V2.1.

Why we don't extend D's `MockPaymentAdapter` directly
----------------------------------------------------
The W1 stub `MockPaymentAdapter.create/confirm/query` is a stateless
pure-function shim: it generates a fake `channel_txn_id` and
immediately returns `status="succeeded"`. That shape is great for
testing the adapter contract in isolation, but it can't drive an
auto-notify (needs shared state) and it can't persist anything back
to the order row. W6-2 spec calls out exactly those two
responsibilities — so we layer them here instead of overloading the
adapter.
"""
import asyncio
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.order import Order, OrderStatusHistory
from app.services.audit import record_audit


_log = get_logger()


# --------------------------------------------------------------------------- #
# Public dataclasses                                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CreateOrderResult:
    """What `create_order` returns to the API layer."""

    order_no: str
    trade_no: str
    code_url: str
    prepay_id: str
    expired_at: datetime
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderPaymentStatus:
    """Snapshot of a single order's payment state — what `query_order` returns."""

    order_no: str
    trade_no: Optional[str]
    status: str           # pending | paid | closed | failed
    paid_at: Optional[datetime]
    amount_cents: int
    currency: str
    raw: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# In-memory notify scheduler                                                   #
# --------------------------------------------------------------------------- #
# Why module-level state instead of a class attribute?  Tests drop_all the DB
# between cases; we want the notify queue to be wiped too — a module-level
# dict is naturally cleared by import reload between pytest sessions. A class
# attribute would leak across cases via pytest's fixture caching.
_PENDING_NOTIFIES: dict[str, asyncio.Task[None]] = {}


def _utcnow() -> datetime:
    """Naive UTC, matching the rest of the codebase (no tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# PaymentProvider                                                              #
# --------------------------------------------------------------------------- #
class PaymentProvider:
    """Mock payment facade — wraps the lower-level adapter with auto-notify.

    Lifecycle of an order:
      create_order(order_no, amount_cents, desc) → returns CreateOrderResult
      → 1s later, internal task fires `handle_notify(order_no)` →
      status flips to "paid" and the trade_no + paid_at are persisted
      onto `orders.extra["payment"]`.

    Thread / async safety:
      All mutation goes through `AsyncSession` (no shared mutable state
      outside `_PENDING_NOTIFIES`). The pending task map is keyed by
      `order_no`; we cancel + replace any prior task for the same order
      so a "create → close → create" flow doesn't fire a stale notify.
    """

    # Per V2 §4.5 spec: a created mock order expires 2 hours from creation.
    MOCK_ORDER_TTL_SECONDS: int = 2 * 60 * 60
    # Per W6-2 spec: auto-notify fires 1s after create_order.
    AUTO_NOTIFY_DELAY_SECONDS: float = 1.0

    # ------------------------------------------------------------------ #
    # create_order                                                       #
    # ------------------------------------------------------------------ #
    async def create_order(
        self,
        db: AsyncSession,
        *,
        order_no: str,
        amount_cents: int,
        desc: str = "",
        currency: str = "USD",
    ) -> CreateOrderResult:
        """Create a fake trade, return code_url (WxPay-style bizpayurl).

        Side-effects:
          - Persists `{payment: {status: pending, trade_no, ...}}` to
            `orders.extra` (JSON) and writes an OrderStatusHistory row
            with `note="payment: pending"` so the audit trail is
            visible in `GET /orders/{no}`.
          - Schedules an asyncio task that, after 1s, calls
            `handle_notify(order_no)` to flip status → paid.
          - Cancels any prior pending notify for the same order_no.
        """
        if amount_cents <= 0:
            raise ValueError(f"amount_cents must be positive, got {amount_cents}")

        order = await self._load_order(db, order_no)
        extra, reuse_blob, _superseded = self._prepare_create_payment(
            order,
            amount_cents=amount_cents,
            currency=currency,
        )
        if reuse_blob is not None:
            return self._blob_to_create_result(order_no, reuse_blob)

        # Cancel any pending auto-notify for this order (e.g. re-pay flow).
        prior = _PENDING_NOTIFIES.pop(order_no, None)
        if prior is not None and not prior.done():
            prior.cancel()

        # Mock trade_no is opaque + unique-enough for log correlation.
        trade_no = "MOCK" + secrets.token_hex(8).upper()
        prepay_id = "PREPAY" + secrets.token_hex(6).upper()
        # W6-2 spec: code_url is the WxPay bizpayurl shape, prefixed MOCK
        # so a real WxPay client never mistakes it for a real charge URL.
        code_url = f"weixin://wxpay/bizpayurl?pr=MOCK_{trade_no}"
        expired_at = _utcnow() + timedelta(seconds=self.MOCK_ORDER_TTL_SECONDS)

        payment_blob = {
            "trade_no": trade_no,
            "prepay_id": prepay_id,
            "code_url": code_url,
            "status": "pending",
            "amount_cents": int(amount_cents),
            "currency": currency,
            "desc": desc,
            "created_at": _utcnow().isoformat(),
            "expired_at": expired_at.isoformat(),
            "paid_at": None,
        }

        # Merge into existing extra["payment"] so we don't clobber other keys.
        extra["payment"] = payment_blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        # Note: order.status is the initial status — no transition to record.
        # Fix (agent2 2026-06-30): removed redundant from_status==to_status row.
        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.create",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "trade_no": trade_no,
                "amount_cents": int(amount_cents),
                "currency": currency,
            },
        )
        await db.commit()
        await db.refresh(order)

        # Fire-and-forget auto-notify. We capture the loop so the task
        # is created in the same loop the caller is in (uvicorn's main
        # loop in prod; pytest's loop in tests).
        loop = asyncio.get_running_loop()
        task = loop.create_task(
            self._auto_notify(order_no=order_no, trade_no=trade_no),
            name=f"payment-auto-notify-{order_no}",
        )
        _PENDING_NOTIFIES[order_no] = task

        _log.info(
            "payment created order_no={} trade_no={} amount_cents={} currency={}",
            order_no,
            trade_no,
            amount_cents,
            currency,
        )

        return CreateOrderResult(
            order_no=order_no,
            trade_no=trade_no,
            code_url=code_url,
            prepay_id=prepay_id,
            expired_at=expired_at,
            raw=payment_blob,
        )

    # ------------------------------------------------------------------ #
    # query_order                                                        #
    # ------------------------------------------------------------------ #
    async def query_order(
        self, db: AsyncSession, *, order_no: str
    ) -> OrderPaymentStatus:
        """Read the current payment status for an order.

        Returns a normalised snapshot regardless of whether the order
        has been paid, closed, or never had `create_order` called.
        The API layer renders this as `GET /api/v2/payment/{order_no}`.
        """
        order = await self._load_order(db, order_no)
        blob = self._load_extra(order).get("payment") or {}
        return OrderPaymentStatus(
            order_no=order_no,
            trade_no=blob.get("trade_no"),
            status=blob.get("status") or "none",
            paid_at=_parse_iso(blob.get("paid_at")),
            amount_cents=int(blob.get("amount_cents") or 0),
            currency=blob.get("currency") or "USD",
            raw=blob,
        )

    # ------------------------------------------------------------------ #
    # handle_notify                                                      #
    # ------------------------------------------------------------------ #
    async def handle_notify(
        self,
        db: AsyncSession,
        *,
        order_no: str,
        trade_no: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Process a payment-callback payload.

        For the Mock provider, this is what `_auto_notify` calls after
        the 1s grace period. For a real WxPay integration, this is what
        `/api/v2/payment/notify` will receive (signed XML/JSON). Either
        way the contract is the same: idempotently flip the order's
        `extra["payment"].status` from `pending` → `paid`, set
        `paid_at`, and write an OrderStatusHistory + audit row.

        Returns True if this call actually transitioned pending → paid,
        False if the order was already paid (idempotent replay) or had
        no payment record yet (e.g. someone POST'd /notify without
        first calling /create — we 404 in the API layer instead, so
        this method is reached only when `extra["payment"]` exists).
        """
        order = await self._load_order(db, order_no)
        extra = self._load_extra(order)
        blob = extra.get("payment")
        if not blob:
            _log.warning(
                "handle_notify: no payment blob for order_no={}", order_no
            )
            return False

        # Idempotency: if already paid (and trade_no matches, if supplied),
        # the caller still gets a success — that's what "idempotent" means.
        # Mismatched trade_no is a programmer error in mock mode but in V2.1
        # with real channel it would be a tampered callback → reject.
        current_status = blob.get("status")
        if current_status == "paid":
            if trade_no and trade_no != blob.get("trade_no"):
                _log.warning(
                    "handle_notify: trade_no mismatch order_no={} "
                    "expected={} got={}",
                    order_no,
                    blob.get("trade_no"),
                    trade_no,
                )
                return False
            _log.info(
                "handle_notify: order_no={} already paid (idempotent replay)",
                order_no,
            )
            return True

        if current_status == "refunded":
            _log.warning(
                "handle_notify: order_no={} already refunded; ignoring callback",
                order_no,
            )
            return False

        # Refuse to revive a closed/failed payment.
        if current_status not in (None, "pending"):
            _log.warning(
                "handle_notify: order_no={} status={} not eligible",
                order_no,
                current_status,
            )
            return False

        if trade_no and blob.get("trade_no") and trade_no != blob.get("trade_no"):
            _log.warning(
                "handle_notify: stale trade_no order_no={} expected={} got={}",
                order_no,
                blob.get("trade_no"),
                trade_no,
            )
            return False

        paid_at = _utcnow()
        blob["status"] = "paid"
        blob["paid_at"] = paid_at.isoformat()
        if trade_no:
            blob["trade_no"] = trade_no
        if payload:
            blob["notify_payload"] = payload
        extra["payment"] = blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        # V2 §4.2.4: payment completion flips order.status 'created' →
        # 'submitted' (payment serves as the user's confirmation to push the
        # order into the processing queue). Earlier this was intentionally
        # left to manual admin approval only (verifier #1 W17 audit caught
        # the gap).
        # Fix (agent2 2026-06-30): capture prev_status BEFORE mutation so the
        # history record is accurate; only write a row when status actually changed.
        prev_status = order.status
        if prev_status == "created":
            # Honour 1h payment lock — late callbacks need manual refund.
            lock_deadline = order.locked_until
            if lock_deadline and paid_at > lock_deadline:
                order.status = "cancelled"
                order.closed_at = paid_at
                self.db_add_status_history(
                    db,
                    order_id=order.id,
                    from_status=prev_status,
                    to_status="cancelled",
                    source="payment",
                    note="payment received after lock expired — needs manual refund",
                )
                await db.commit()
                _log.warning(
                    "handle_notify: late payment after lock order_no={} locked_until={}",
                    order_no,
                    lock_deadline,
                )
                return False
            order.status = "paid"
            order.paid_at = paid_at
        elif prev_status == "cancelled":
            _log.warning(
                "handle_notify: order already cancelled order_no={}", order_no,
            )
            return False
        elif prev_status in ("paid", "completed"):
            pass  # idempotent replay — payment blob already marked paid above
        elif prev_status in ("submitted", "reviewing", "approved"):
            # Legacy rows: keep status, still record payment in extra blob
            if order.paid_at is None:
                order.paid_at = paid_at
        else:
            _log.warning(
                "handle_notify: order_no={} status={} not eligible for payment",
                order_no,
                prev_status,
            )
            return False

        new_status = order.status
        if prev_status != new_status:
            self.db_add_status_history(
                db,
                order_id=order.id,
                from_status=prev_status,
                to_status=new_status,
                source="payment",
                note=f"payment: status {prev_status}→{new_status} trade_no={blob.get('trade_no')}",
            )
        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.notify",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "trade_no": blob.get("trade_no"),
                "paid_at": paid_at.isoformat(),
            },
        )
        await db.commit()
        await db.refresh(order)
        _log.info(
            "payment notified order_no={} trade_no={} paid_at={}",
            order_no,
            blob.get("trade_no"),
            paid_at.isoformat(),
        )

        # B-W9-3 — Affiliate hook on payment completion. Best-effort,
        # never fails the payment response. Lazy-import to avoid a
        # load-time cycle (payment_provider is itself imported by the
        # order_service layer through the affiliate_events seam).
        from app.services.affiliate_events import on_payment_completed

        try:
            await on_payment_completed(order)
        except Exception as exc:  # noqa: BLE001 — defensive
            _log.warning(
                "handle_notify affiliate hook swallowed order_no={} err={}",
                order_no, exc,
            )

        return True

    # ------------------------------------------------------------------ #
    # close_order                                                        #
    # ------------------------------------------------------------------ #
    async def close_order(
        self, db: AsyncSession, *, order_no: str
    ) -> OrderPaymentStatus:
        """Close an unpaid order — flip `pending → closed`.

        Raises ValueError if the order was already paid (a paid order
        must be refunded, not closed; that's V2.1 scope).
        """
        order = await self._load_order(db, order_no)
        extra = self._load_extra(order)
        blob = extra.get("payment")
        if not blob:
            raise LookupError(f"no payment record for order_no={order_no}")
        if blob.get("status") == "paid":
            raise ValueError(
                f"order_no={order_no} is already paid; refund instead of close"
            )

        # Cancel any pending auto-notify — we don't want it to fire
        # after we've explicitly closed the order.
        prior = _PENDING_NOTIFIES.pop(order_no, None)
        if prior is not None and not prior.done():
            prior.cancel()

        blob["status"] = "closed"
        blob["closed_at"] = _utcnow().isoformat()
        extra["payment"] = blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        self.db_add_status_history(
            db,
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            source="payment",
            note=f"payment: closed trade_no={blob.get('trade_no')}",
        )
        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.close",
            target_type="order",
            target_id=order.id,
            payload={"order_no": order_no, "trade_no": blob.get("trade_no")},
        )
        await db.commit()
        await db.refresh(order)
        _log.info("payment closed order_no={}", order_no)

        return OrderPaymentStatus(
            order_no=order_no,
            trade_no=blob.get("trade_no"),
            status="closed",
            paid_at=_parse_iso(blob.get("paid_at")),
            amount_cents=int(blob.get("amount_cents") or 0),
            currency=blob.get("currency") or "USD",
            raw=blob,
        )

    # ------------------------------------------------------------------ #
    # refund_order                                                       #
    # ------------------------------------------------------------------ #
    async def refund_order(
        self,
        db: AsyncSession,
        *,
        order_no: str,
        amount_cents: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> OrderPaymentStatus:
        """Refund a paid order — mock channel flips `paid → refunded`.

        Persists refund metadata on `orders.extra["payment"]` and writes
        `payment.refund` audit. Real Stripe refund lives in StripePaymentProvider.
        """
        order = await self._load_order(db, order_no)
        extra = self._load_extra(order)
        blob = extra.get("payment")
        if not blob:
            raise LookupError(f"no payment record for order_no={order_no}")
        pay_status = blob.get("status")
        if pay_status == "refunded":
            _log.info("payment refund skipped (already refunded) order_no={}", order_no)
            return OrderPaymentStatus(
                order_no=order_no,
                trade_no=blob.get("trade_no"),
                status="refunded",
                paid_at=_parse_iso(blob.get("paid_at")),
                amount_cents=int(blob.get("amount_cents") or 0),
                currency=blob.get("currency") or "USD",
                raw=blob,
            )
        if pay_status != "paid":
            raise ValueError(
                f"order_no={order_no} payment status is {pay_status!r}; cannot refund"
            )

        refund_cents = int(amount_cents or blob.get("amount_cents") or 0)
        if refund_cents <= 0:
            raise ValueError(f"refund amount must be positive for order_no={order_no}")

        refund_trade_no = "REFUND" + secrets.token_hex(8).upper()
        refunded_at = _utcnow()
        blob["status"] = "refunded"
        blob["refunded_at"] = refunded_at.isoformat()
        blob["refund_amount_cents"] = refund_cents
        blob["refund_trade_no"] = refund_trade_no
        if reason:
            blob["refund_reason"] = reason[:500]
        extra["payment"] = blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        self.db_add_status_history(
            db,
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            source="payment",
            note=f"payment: refunded trade_no={blob.get('trade_no')} refund={refund_trade_no}",
        )
        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.refund",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "trade_no": blob.get("trade_no"),
                "refund_trade_no": refund_trade_no,
                "refund_amount_cents": refund_cents,
            },
        )
        # C-05: refund immediately cancels plugin authorization
        from app.core.ds160 import revoke_order_ds160
        if revoke_order_ds160(order):
            await record_audit(
                db,
                actor_type="system",
                actor_id=0,
                action="ds160.code.revoked_on_refund",
                target_type="order",
                target_id=order.id,
                payload={"order_no": order_no},
            )
        await db.commit()
        await db.refresh(order)
        _log.info(
            "payment refunded order_no={} refund_trade_no={} cents={}",
            order_no,
            refund_trade_no,
            refund_cents,
        )

        return OrderPaymentStatus(
            order_no=order_no,
            trade_no=blob.get("trade_no"),
            status="refunded",
            paid_at=_parse_iso(blob.get("paid_at")),
            amount_cents=int(blob.get("amount_cents") or 0),
            currency=blob.get("currency") or "USD",
            raw=blob,
        )

    # ------------------------------------------------------------------ #
    # Internal: order loading + extra-json helpers                       #
    # ------------------------------------------------------------------ #
    async def _load_order(
        self, db: AsyncSession, order_no: str
    ) -> Order:
        order = await db.scalar(select(Order).where(Order.order_no == order_no))
        if order is None:
            raise LookupError(f"order_no={order_no} not found")
        return order

    @staticmethod
    def _load_extra(order: Order) -> dict[str, Any]:
        if not order.extra:
            return {}
        try:
            data = json.loads(order.extra)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _archive_payment_attempt(
        self, extra: dict[str, Any], blob: dict[str, Any], *, reason: str
    ) -> None:
        """Append a superseded payment blob for audit (duplicate trade_no trail)."""
        history = extra.get("payment_history")
        if not isinstance(history, list):
            history = []
        archived = dict(blob)
        archived["archived_at"] = _utcnow().isoformat()
        archived["archive_reason"] = reason
        history.append(archived)
        extra["payment_history"] = history

    def _blob_to_create_result(
        self, order_no: str, blob: dict[str, Any]
    ) -> CreateOrderResult:
        expired_at = _parse_iso(blob.get("expired_at"))
        if expired_at is None:
            expired_at = _utcnow() + timedelta(seconds=self.MOCK_ORDER_TTL_SECONDS)
        return CreateOrderResult(
            order_no=order_no,
            trade_no=str(blob.get("trade_no") or ""),
            code_url=str(blob.get("code_url") or ""),
            prepay_id=str(blob.get("prepay_id") or blob.get("client_secret") or ""),
            expired_at=expired_at,
            raw=blob,
        )

    def _prepare_create_payment(
        self,
        order: Order,
        *,
        amount_cents: int,
        currency: str,
    ) -> tuple[dict[str, Any], Optional[dict[str, Any]], Optional[str]]:
        """Resolve idempotent create / supersede before issuing a new trade_no.

        Returns:
            extra — mutable orders.extra dict
            reuse_blob — when set, caller must return existing payment as-is
            superseded_trade_no — when set, caller should cancel old channel intent

        Raises:
            ValueError: order already paid (duplicate payment forbidden).
        """
        extra = self._load_extra(order)
        blob = extra.get("payment")
        if not isinstance(blob, dict) or not blob:
            return extra, None, None

        status = blob.get("status")
        if status == "paid":
            raise ValueError(
                f"order_no={order.order_no} is already paid; duplicate payment rejected"
            )

        if status == "refunded":
            self._archive_payment_attempt(extra, blob, reason="superseded_after_refund")
            extra.pop("payment", None)
            return extra, None, None

        if status == "pending":
            expired_at = _parse_iso(blob.get("expired_at"))
            same_amount = int(blob.get("amount_cents") or 0) == int(amount_cents)
            same_currency = (blob.get("currency") or "USD").upper() == currency.upper()
            not_expired = expired_at is None or expired_at > _utcnow()
            if same_amount and same_currency and not_expired:
                _log.info(
                    "payment create idempotent replay order_no={} trade_no={}",
                    order.order_no,
                    blob.get("trade_no"),
                )
                return extra, blob, None
            superseded = blob.get("trade_no")
            self._archive_payment_attempt(extra, blob, reason="superseded_pending")
            extra.pop("payment", None)
            return extra, None, str(superseded) if superseded else None

        if status in ("closed", "failed"):
            superseded = blob.get("trade_no")
            self._archive_payment_attempt(
                extra, blob, reason=f"superseded_{status}"
            )
            extra.pop("payment", None)
            return extra, None, str(superseded) if superseded else None

        superseded = blob.get("trade_no")
        self._archive_payment_attempt(extra, blob, reason="superseded_unknown")
        extra.pop("payment", None)
        return extra, None, str(superseded) if superseded else None

    @staticmethod
    def db_add_status_history(
        db: AsyncSession,
        *,
        order_id: int,
        from_status: Optional[str],
        to_status: str,
        source: str,
        note: str,
    ) -> None:
        db.add(
            OrderStatusHistory(
                order_id=order_id,
                from_status=from_status,
                to_status=to_status,
                source=source,
                note=note,
            )
        )

    # ------------------------------------------------------------------ #
    # Internal: auto-notify task                                         #
    # ------------------------------------------------------------------ #
    async def _auto_notify(self, *, order_no: str, trade_no: str) -> None:
        """Fire-and-forget task: sleep 1s, then open a fresh session and
        call `handle_notify`.

        We open a fresh session (rather than reusing the request's)
        because the request session is closed by the time this fires.
        Using a fresh session also keeps the test fixture lifecycle
        predictable — each test gets its own DB and its own engine,
        and we want the auto-notify to target that same DB.
        """
        try:
            await asyncio.sleep(self.AUTO_NOTIFY_DELAY_SECONDS)
        except asyncio.CancelledError:
            _log.info("auto-notify cancelled order_no={}", order_no)
            return

        from app.core.db import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                await self.handle_notify(
                    session, order_no=order_no, trade_no=trade_no
                )
        except Exception:  # pragma: no cover - background best-effort
            _log.exception("auto-notify failed order_no={}", order_no)
        finally:
            # Drop our handle so a re-pay flow can register a fresh task.
            _PENDING_NOTIFIES.pop(order_no, None)


# --------------------------------------------------------------------------- #
# Factory (singleton, per-process)                                            #
# --------------------------------------------------------------------------- #
_provider_singleton: Optional[PaymentProvider] = None
_provider_channel: Optional[str] = None


def get_payment_provider() -> PaymentProvider:
    """Module-level accessor — keeps a single provider per process.

    Routing:
      - ``payment_channel=mock`` (default) → Mock ``PaymentProvider``.
      - ``payment_channel=stripe`` + non-blank ``STRIPE_SECRET_KEY`` →
        ``StripePaymentProvider``.
      - ``payment_channel=stripe`` but key missing → falls back to Mock
        with a warning (dev/test stays credential-free).
    """
    global _provider_singleton, _provider_channel
    settings = get_settings()
    channel = settings.payment_channel
    if _provider_singleton is None or _provider_channel != channel:
        if channel == "stripe" and settings.stripe_secret_key:
            _provider_singleton = StripePaymentProvider()
            _log.info("payment provider: stripe (V2.1)")
        else:
            if channel == "stripe" and not settings.stripe_secret_key:
                _log.warning(
                    "payment_channel=stripe but STRIPE_SECRET_KEY empty; "
                    "falling back to Mock"
                )
            _provider_singleton = PaymentProvider()
            _log.info("payment provider: mock")
        _provider_channel = channel
    return _provider_singleton


def reset_payment_provider_for_tests() -> None:
    """Clear the singleton + pending notifies between tests.

    Designed to be safe to call during pytest teardown when the event
    loop may already be closing — we swallow loop-closed errors because
    the tasks themselves were created in a different loop (per-test
    loop created by pytest-asyncio) and would have been cancelled by
    the loop's natural shutdown anyway.
    """
    global _provider_singleton, _provider_channel
    _provider_singleton = None
    _provider_channel = None
    # Cancel any stragglers so pytest doesn't leak running tasks between cases.
    for t in _PENDING_NOTIFIES.values():
        if not t.done():
            try:
                t.cancel()
            except RuntimeError:
                # Event loop already closed — task will be GC'd.
                pass
    _PENDING_NOTIFIES.clear()


# --------------------------------------------------------------------------- #
# StripePaymentProvider — V2.1 真接 (W10-4 wire-up)                          #
# --------------------------------------------------------------------------- #
# Per Mavis 2026-06-12 10:54 decision: 支付全 Mock, 后期 V2.1 阶段再接.
# Per W10-4 (2026-06-12 23:00): Stripe 4 method 真接实现.
#
# Activation gate (still present in V2.1 — no network unless credentialed):
#   - `STRIPE_SECRET_KEY` is non-blank → `self.stripe` binds the SDK,
#     all four methods + `payout` route to real Stripe API calls.
#   - blank → `self.stripe is None`, every method raises
#     `NotImplementedError("V2.1 阶段接真 SDK")`. The Mock provider above
#     remains the V2 path. **V2 ships credential-free by design.**
#
# V2.1 design contract (mirrors Mock):
#   - `create_order` → `stripe.PaymentIntent.create_async(amount=...,
#     currency='usd', metadata={'order_no': ...})`. We pick PaymentIntent
#     over Checkout.Session because we control the front-end (we render
#     the card form ourselves, see W9-2 frontend), and PaymentIntent
#     gives us a `client_secret` for Stripe.js confirmCardPayment().
#   - `query_order` → `stripe.PaymentIntent.retrieve_async(intent_id)`.
#     The intent_id is persisted in `orders.extra["payment"].trade_no`.
#   - `handle_notify` → `stripe.Webhook.construct_event(payload,
#     sig_header, secret)`. Signature is taken from the inbound webhook's
#     `Stripe-Signature` header. Returns the verified `Event` object; we
#     then look up the order by `event.data.object.metadata.order_no` and
#     flip `extra["payment"].status`.
#   - `close_order` → `stripe.PaymentIntent.cancel_async(intent_id)` for
#     unpaid intents (Stripe rejects cancel on already-succeeded intents
#     — we surface that as a 4013 PAYMENT_ALREADY_PAID error in the API
#     layer).
#   - `payout(partner_id, period)` → `stripe.Transfer.create_async(
#     amount=..., currency='usd', destination=partner_account_id,
#     metadata={'partner_id': ..., 'period': ...})`. V2.1 affiliate
#     settlement — uses the partner's Stripe Connect account id, which
#     the affiliate service stores in its own row (out of scope here,
#     we accept a `partner_account_id: str` arg so the affiliate service
#     can wire it).
#
# Mtime/credential safety:
#   - Never log the secret. Never echo it in errors. Never commit it.
#   - macOS Keychain-backed env (preferred in V2.1 prod) — see the
#     config.py docstring for the launch recipe.
#   - Tests inject a synthetic key via `monkeypatch.setattr(
#     'app.services.payment_provider.get_settings', ...)` and call the
#     async SDK methods. The `httpx` library that stripe uses is
#     intercepted by `respx` (out of scope) or simply rejected at the
#     `if self.stripe is None` gate if no key is set.
def _configure_stripe_network(stripe_module) -> None:
    """Keep Stripe HTTPS off local HTTP_PROXY (common 403 on CN dev proxies)."""
    import os

    for key in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(key, "")
        if "api.stripe.com" not in current:
            os.environ[key] = ",".join(
                part for part in (current, "api.stripe.com") if part
            )
    # Recreate lazily so httpx picks up the updated NO_PROXY.
    stripe_module.default_http_client = None


class StripePaymentProvider(PaymentProvider):
    """V2.1 真接 — `PaymentIntent` + `Webhook` + `Transfer` 调真 SDK.

    **All methods raise `NotImplementedError` when `STRIPE_SECRET_KEY`
    is blank** (V2 dev/test path). V2.1 prod path with a real test/live
    key routes through the real Stripe API.

    The public surface matches `PaymentProvider` (create_order /
    query_order / handle_notify / close_order) so the API layer can
    swap Mock↔Stripe without any caller-visible change. The extra
    `payout()` method is V2.1-only — affiliates don't exist in V2.

    Inherits the helper methods `_load_order` / `_load_extra` /
    `db_add_status_history` from `PaymentProvider` so the persistence
    shape (`orders.extra["payment"]` JSON + `OrderStatusHistory` rows
    + audit log) is identical between Mock and Stripe — the API
    layer never needs to branch on provider.
    """

    # Mirror Mock's public surface so callers don't need to branch.
    MOCK_ORDER_TTL_SECONDS: int = 2 * 60 * 60
    AUTO_NOTIFY_DELAY_SECONDS: float = 1.0

    def __init__(self) -> None:
        """Import + bind the SDK lazily, gated by `stripe_secret_key`.

        Why lazy: importing `stripe` at module top-level would slow down
        every pytest collection even when only Mock is in use. Importing
        here keeps the Mock-only path (V2 dev/test) zero-cost on the
        SDK side, and pays the import cost only on the V2.1 path that
        actually needs the SDK.
        """
        import stripe as _stripe  # local import — see docstring above

        secret = get_settings().stripe_secret_key
        if secret:
            # Real key present → V2.1 path. Configure the SDK in-place.
            _configure_stripe_network(_stripe)
            _stripe.api_key = secret
            self.stripe = _stripe
            self.webhook_secret = get_settings().stripe_webhook_secret
            self.payout_account_id = get_settings().stripe_payout_account_id
            _log.info(
                "StripePaymentProvider: live SDK configured (V2.1+ mode) "
                "key_prefix={}",
                secret[:8] + "***" if len(secret) > 8 else "***",
            )
        else:
            # No key → stub mode. Every method will raise.
            self.stripe = None
            self.webhook_secret = ""
            self.payout_account_id = ""
            _log.info(
                "StripePaymentProvider: stub mode (no STRIPE_SECRET_KEY); "
                "V2 ships with Mock only per Mavis 2026-06-12 10:54"
            )

    # We do NOT call super().__init__() — `PaymentProvider.__init__` is
    # the default object init (no state), and skipping the call lets the
    # SDK lazy-import stay lazy.

    def _require_stripe(self) -> None:
        """Internal guard: stub mode raises here; V2.1+ passes through."""
        if self.stripe is None:
            raise NotImplementedError(
                "StripePaymentProvider requires STRIPE_SECRET_KEY in .env "
                "(V2.1 阶段接真 SDK; V2 ships with Mock only)"
            )

    # ------------------------------------------------------------------ #
    # V2.1 真接 create_order (stripe.PaymentIntent.create_async)         #
    # ------------------------------------------------------------------ #
    async def create_order(
        self,
        db: AsyncSession,
        *,
        order_no: str,
        amount_cents: int,
        desc: str = "",
        currency: str = "USD",
    ) -> CreateOrderResult:
        """Create a real Stripe PaymentIntent, persist to `extra["payment"]`.

        Steps:
          1. Validate `amount_cents > 0`.
          2. Call `stripe.PaymentIntent.create_async(...)` with
             `amount = amount_cents` (Stripe takes the smallest unit —
             USD has 2 decimal places, so 100 cents = $1.00). Pass
             `metadata={"order_no": ...}` so the webhook can resolve
             back to the order without us keeping a separate map.
          3. Build a `CreateOrderResult` with `trade_no = intent.id`,
             `code_url` = `client_secret` (front-end uses Stripe.js
             confirmCardPayment with this token), and a 2h TTL.
          4. Persist `{payment: {trade_no, status, client_secret, ...}}`
             to `orders.extra` (same shape as Mock) and write a status
             history row.

        Side-effects:
          - One outbound HTTPS call to `api.stripe.com/v1/payment_intents`.
          - One DB write (`orders.extra` + `OrderStatusHistory` + audit).
        """
        if amount_cents <= 0:
            raise ValueError(f"amount_cents must be positive, got {amount_cents}")
        self._require_stripe()

        order = await self._load_order(db, order_no)
        extra, reuse_blob, superseded_trade_no = self._prepare_create_payment(
            order,
            amount_cents=amount_cents,
            currency=currency,
        )
        if reuse_blob is not None:
            return self._blob_to_create_result(order_no, reuse_blob)

        if superseded_trade_no:
            try:
                await self.stripe.PaymentIntent.cancel_async(superseded_trade_no)
                _log.info(
                    "stripe superseded pending intent order_no={} trade_no={}",
                    order_no,
                    superseded_trade_no,
                )
            except Exception as exc:  # noqa: BLE001 — best-effort
                _log.warning(
                    "stripe cancel superseded intent failed order_no={} "
                    "trade_no={} err={}",
                    order_no,
                    superseded_trade_no,
                    exc,
                )

        # Create the real PaymentIntent via the async SDK call.
        intent = await self.stripe.PaymentIntent.create_async(
            amount=int(amount_cents),
            currency=currency.lower(),
            description=desc or f"Visa MVP order {order_no}",
            metadata={"order_no": order_no, "source": "visa-mvp-v2.1"},
            # We do NOT set `confirm=True` here — the front-end confirms
            # via Stripe.js after collecting card details. The webhook
            # is the source of truth for "paid".
            automatic_payment_methods={"enabled": True},
        )

        trade_no = intent.id  # `pi_3Nx...`
        client_secret = intent.client_secret
        expired_at = _utcnow() + timedelta(seconds=self.MOCK_ORDER_TTL_SECONDS)
        # For Stripe we use `client_secret` as the "code_url" field (it
        # plays the same role as the WxPay bizpayurl — a token the
        # front-end hands to Stripe.js to complete payment).
        code_url = client_secret or ""

        payment_blob = {
            "trade_no": trade_no,
            "client_secret": client_secret,
            "code_url": code_url,
            "status": "pending",
            "stripe_status": intent.status,
            "amount_cents": int(amount_cents),
            "currency": currency,
            "desc": desc,
            "created_at": _utcnow().isoformat(),
            "expired_at": expired_at.isoformat(),
            "paid_at": None,
            "provider": "stripe",
        }

        # Persist to orders.extra (same shape as Mock).
        extra["payment"] = payment_blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        # Note: order.status is the initial status — no transition to record.
        # Fix (agent2 2026-06-30): removed redundant from_status==to_status row.
        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.create",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "trade_no": trade_no,
                "amount_cents": int(amount_cents),
                "currency": currency,
                "provider": "stripe",
            },
        )
        await db.commit()
        await db.refresh(order)

        _log.info(
            "stripe payment created order_no={} trade_no={} amount_cents={} "
            "currency={} status={}",
            order_no, trade_no, amount_cents, currency, intent.status,
        )

        return CreateOrderResult(
            order_no=order_no,
            trade_no=trade_no,
            code_url=code_url,
            prepay_id=client_secret or "",
            expired_at=expired_at,
            raw=payment_blob,
        )

    # ------------------------------------------------------------------ #
    # V2.1 真接 query_order (stripe.PaymentIntent.retrieve_async)         #
    # ------------------------------------------------------------------ #
    async def query_order(
        self, db: AsyncSession, *, order_no: str
    ) -> OrderPaymentStatus:
        """Read the current payment status for a real Stripe-backed order.

        We use the `trade_no` stored in `extra["payment"]` as the
        PaymentIntent id, call `stripe.PaymentIntent.retrieve_async`,
        and map Stripe's status (`requires_payment_method` /
        `requires_confirmation` / `requires_action` / `processing` /
        `requires_capture` / `canceled` / `succeeded`) onto the V2
        normalised shape (`pending` / `paid` / `closed` / `failed`).
        """
        self._require_stripe()
        order = await self._load_order(db, order_no)
        blob = self._load_extra(order).get("payment") or {}
        trade_no = blob.get("trade_no")
        if blob.get("status") == "refunded":
            return OrderPaymentStatus(
                order_no=order_no,
                trade_no=trade_no,
                status="refunded",
                paid_at=_parse_iso(blob.get("paid_at")),
                amount_cents=int(blob.get("amount_cents") or 0),
                currency=blob.get("currency") or "USD",
                raw=blob,
            )
        if not trade_no:
            return OrderPaymentStatus(
                order_no=order_no, trade_no=None, status="none",
                paid_at=None, amount_cents=0, currency="USD", raw=blob,
            )

        try:
            intent = await self.stripe.PaymentIntent.retrieve_async(trade_no)
        except Exception as exc:  # noqa: BLE001 — best-effort
            _log.warning(
                "stripe retrieve failed order_no={} trade_no={} err={}",
                order_no, trade_no, exc,
            )
            # Fall back to the persisted snapshot so the front-end still
            # gets a coherent response. V2.1 prod should also wire a
            # retry / circuit breaker here.
            return OrderPaymentStatus(
                order_no=order_no, trade_no=trade_no,
                status=blob.get("status") or "unknown",
                paid_at=_parse_iso(blob.get("paid_at")),
                amount_cents=int(blob.get("amount_cents") or 0),
                currency=blob.get("currency") or "USD",
                raw={"intent_retrieve_failed": str(exc), **blob},
            )

        # Map Stripe status → V2 normalised status.
        # Reference: https://stripe.com/docs/payments/intents#intent-statuses
        _STRIPE_STATUS_MAP = {
            "requires_payment_method": "pending",
            "requires_confirmation": "pending",
            "requires_action": "pending",
            "processing": "pending",
            "requires_capture": "pending",
            "succeeded": "paid",
            "canceled": "closed",
        }
        normalised = _STRIPE_STATUS_MAP.get(intent.status, "failed")
        paid_at = _parse_iso(blob.get("paid_at"))
        # If Stripe says succeeded but our blob doesn't yet have paid_at
        # (e.g. webhook hasn't landed), sync DB so Phase A polling works
        # without requiring stripe CLI immediately.
        if normalised == "paid" and blob.get("status") != "paid":
            extra = self._load_extra(order)
            payment_blob = dict(extra.get("payment") or blob)
            payment_blob["status"] = "paid"
            payment_blob["paid_at"] = _utcnow().isoformat()
            payment_blob["trade_no"] = intent.id
            if getattr(intent, "amount_received", None) is not None:
                payment_blob["amount_received_cents"] = int(intent.amount_received)
            extra["payment"] = payment_blob
            order.extra = json.dumps(extra, ensure_ascii=False)
            prev_status = order.status
            if prev_status in ("created", "pending"):
                order.status = "submitted"
                if order.submitted_at is None:
                    order.submitted_at = _utcnow()
                self.db_add_status_history(
                    db,
                    order_id=order.id,
                    from_status=prev_status,
                    to_status="submitted",
                    source="payment",
                    note=f"payment: stripe query sync paid trade_no={intent.id}",
                )
            await db.commit()
            await db.refresh(order)
            blob = payment_blob
            paid_at = _parse_iso(blob.get("paid_at"))
            _log.info(
                "stripe query_order synced paid order_no={} trade_no={}",
                order_no, intent.id,
            )
        elif normalised == "paid" and not paid_at:
            paid_at = _utcnow()

        return OrderPaymentStatus(
            order_no=order_no,
            trade_no=trade_no,
            status=normalised,
            paid_at=paid_at,
            amount_cents=int(blob.get("amount_cents") or 0),
            currency=blob.get("currency") or "USD",
            raw={**blob, "stripe_status": intent.status, "intent_id": intent.id},
        )

    # ------------------------------------------------------------------ #
    # V2.1 真接 handle_notify (stripe.Webhook.construct_event)            #
    # ------------------------------------------------------------------ #
    async def handle_notify(
        self,
        db: AsyncSession,
        *,
        order_no: str,
        trade_no: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Process a real Stripe webhook payload.

        `payload` is the **decoded JSON body** of the POST. The actual
        signature verification is the API layer's job — the API endpoint
        takes the raw body + `Stripe-Signature` header, calls
        `stripe.Webhook.construct_event` itself, and passes the
        resulting `Event` dict (or just the `data.object` slice) to
        us here. We accept the `payload` shape:
            {"type": "payment_intent.succeeded",
             "data": {"object": {"id": "pi_...", "metadata":
              {"order_no": "..."}}}}

        On a verified `payment_intent.succeeded`, we flip the order's
        `extra["payment"].status` from `pending → paid` and stamp
        `paid_at` — same contract as the Mock provider so the API
        layer doesn't need to branch on provider.
        """
        self._require_stripe()
        order = await self._load_order(db, order_no)
        extra = self._load_extra(order)
        blob = extra.get("payment")
        if not blob:
            _log.warning(
                "stripe handle_notify: no payment blob for order_no={}",
                order_no,
            )
            return False

        if payload is None:
            _log.warning(
                "stripe handle_notify: empty payload for order_no={}", order_no
            )
            return False

        event_type = payload.get("type") or ""
        event_object = (payload.get("data") or {}).get("object") or {}
        event_trade_no = event_object.get("id")

        # Idempotency: paid / refunded are terminal for this trade_no.
        if blob.get("status") == "paid":
            if event_trade_no and event_trade_no != blob.get("trade_no"):
                _log.warning(
                    "stripe handle_notify: trade_no mismatch order_no={} "
                    "expected={} got={}",
                    order_no,
                    blob.get("trade_no"),
                    event_trade_no,
                )
                return False
            _log.info(
                "stripe handle_notify: order_no={} already paid (replay)",
                order_no,
            )
            return True

        if blob.get("status") == "refunded":
            _log.warning(
                "stripe handle_notify: order_no={} refunded; ignoring event {}",
                order_no,
                event_type,
            )
            return False

        # Only "succeeded" / "payment_failed" flip the order's status
        # (other events are informational: `payment_intent.created`,
        # `payment_intent.processing`, etc.).
        if event_type == "payment_intent.succeeded":
            if event_trade_no and blob.get("trade_no") and event_trade_no != blob.get("trade_no"):
                _log.warning(
                    "stripe handle_notify: stale intent succeeded order_no={} "
                    "current={} event={}",
                    order_no,
                    blob.get("trade_no"),
                    event_trade_no,
                )
                return True  # ack without mutating current payment
            blob["status"] = "paid"
            blob["paid_at"] = _utcnow().isoformat()
            if event_object.get("id"):
                blob["trade_no"] = event_object["id"]
            if event_object.get("amount_received") is not None:
                blob["amount_received_cents"] = int(
                    event_object["amount_received"]
                )
        elif event_type == "payment_intent.payment_failed":
            blob["status"] = "failed"
            blob["failed_at"] = _utcnow().isoformat()
            blob["failure_message"] = (event_object.get("last_payment_error")
                                       or {}).get("message")
        else:
            # Informational event — log and 200 OK to ack Stripe's retry.
            _log.info(
                "stripe handle_notify: informational event type={} "
                "order_no={}",
                event_type, order_no,
            )
            return True

        if payload:
            blob["notify_payload"] = payload
        extra["payment"] = blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        # Mirror Mock: payment completion flips order.status created/pending → submitted.
        paid_at = None
        if blob.get("paid_at"):
            try:
                paid_at = datetime.fromisoformat(blob["paid_at"])
            except (TypeError, ValueError):
                paid_at = _utcnow()
        prev_status = order.status
        if event_type == "payment_intent.succeeded" and prev_status in ("created", "pending"):
            order.status = "submitted"
            if order.submitted_at is None:
                order.submitted_at = paid_at or _utcnow()
        new_status = order.status
        if prev_status != new_status:
            self.db_add_status_history(
                db,
                order_id=order.id,
                from_status=prev_status,
                to_status=new_status,
                source="payment",
                note=f"payment: stripe paid trade_no={blob.get('trade_no')}",
            )

        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.notify",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "trade_no": blob.get("trade_no"),
                "event_type": event_type,
                "paid_at": blob.get("paid_at"),
            },
        )
        await db.commit()
        await db.refresh(order)
        _log.info(
            "stripe payment notified order_no={} trade_no={} event={} "
            "status={}",
            order_no, blob.get("trade_no"), event_type, blob.get("status"),
        )

        # B-W9-3 — Affiliate hook on payment completion. Best-effort.
        if event_type == "payment_intent.succeeded":
            from app.services.affiliate_events import on_payment_completed
            try:
                await on_payment_completed(order)
            except Exception as exc:  # noqa: BLE001 — defensive
                _log.warning(
                    "stripe handle_notify affiliate hook swallowed "
                    "order_no={} err={}",
                    order_no, exc,
                )

        return True

    # ------------------------------------------------------------------ #
    # V2.1 真接 close_order (stripe.PaymentIntent.cancel_async)           #
    # ------------------------------------------------------------------ #
    async def close_order(
        self, db: AsyncSession, *, order_no: str
    ) -> OrderPaymentStatus:
        """Cancel a real Stripe PaymentIntent.

        Stripe rejects cancel on already-succeeded intents → we surface
        that as a `ValueError("already paid; refund instead of close")`,
        mirroring the Mock provider's error shape so the API layer's
        catch block stays the same.
        """
        self._require_stripe()
        order = await self._load_order(db, order_no)
        extra = self._load_extra(order)
        blob = extra.get("payment")
        if not blob:
            raise LookupError(f"no payment record for order_no={order_no}")
        if blob.get("status") == "paid":
            raise ValueError(
                f"order_no={order_no} is already paid; refund instead of close"
            )
        trade_no = blob.get("trade_no")
        if not trade_no:
            raise LookupError(
                f"no Stripe intent id for order_no={order_no}"
            )

        try:
            await self.stripe.PaymentIntent.cancel_async(trade_no)
        except Exception as exc:  # noqa: BLE001 — best-effort
            _log.warning(
                "stripe cancel failed order_no={} trade_no={} err={}",
                order_no, trade_no, exc,
            )
            # Don't surface Stripe's raw error to the client — fall
            # through with our local state change so the caller still
            # gets a clean closed status.
            # (Common case: intent was already canceled or succeeded
            # between our local status check and the cancel call —
            # Stripe's error tells us which.)

        blob["status"] = "closed"
        blob["closed_at"] = _utcnow().isoformat()
        extra["payment"] = blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        self.db_add_status_history(
            db,
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            source="payment",
            note=f"payment: stripe closed trade_no={trade_no}",
        )
        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.close",
            target_type="order",
            target_id=order.id,
            payload={"order_no": order_no, "trade_no": trade_no,
                     "provider": "stripe"},
        )
        await db.commit()
        await db.refresh(order)
        _log.info("stripe payment closed order_no={}", order_no)

        return OrderPaymentStatus(
            order_no=order_no,
            trade_no=trade_no,
            status="closed",
            paid_at=_parse_iso(blob.get("paid_at")),
            amount_cents=int(blob.get("amount_cents") or 0),
            currency=blob.get("currency") or "USD",
            raw=blob,
        )

    # ------------------------------------------------------------------ #
    # V2.1 真接 refund_order (stripe.Refund.create_async)                  #
    # ------------------------------------------------------------------ #
    async def refund_order(
        self,
        db: AsyncSession,
        *,
        order_no: str,
        amount_cents: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> OrderPaymentStatus:
        """Issue a real Stripe Refund against the order's PaymentIntent."""
        self._require_stripe()
        order = await self._load_order(db, order_no)
        extra = self._load_extra(order)
        blob = extra.get("payment")
        if not blob:
            raise LookupError(f"no payment record for order_no={order_no}")

        pay_status = blob.get("status")
        if pay_status == "refunded":
            _log.info("stripe refund skipped (already refunded) order_no={}", order_no)
            return OrderPaymentStatus(
                order_no=order_no,
                trade_no=blob.get("trade_no"),
                status="refunded",
                paid_at=_parse_iso(blob.get("paid_at")),
                amount_cents=int(blob.get("amount_cents") or 0),
                currency=blob.get("currency") or "USD",
                raw=blob,
            )
        if pay_status != "paid":
            intent_id = blob.get("trade_no")
            if intent_id:
                try:
                    intent = await self.stripe.PaymentIntent.retrieve_async(intent_id)
                    if intent.status == "succeeded":
                        paid_at = _utcnow()
                        blob["status"] = "paid"
                        blob["paid_at"] = blob.get("paid_at") or paid_at.isoformat()
                        pay_status = "paid"
                        extra["payment"] = blob
                        order.extra = json.dumps(extra, ensure_ascii=False)
                        await db.commit()
                except Exception as exc:  # noqa: BLE001
                    _log.warning(
                        "stripe refund pre-sync failed order_no={} err={}",
                        order_no,
                        exc,
                    )
        if pay_status != "paid":
            raise ValueError(
                f"order_no={order_no} payment status is {pay_status!r}; cannot refund"
            )

        intent_id = blob.get("trade_no")
        if not intent_id:
            raise LookupError(f"no Stripe intent id for order_no={order_no}")

        refund_cents = int(amount_cents or blob.get("amount_cents") or 0)
        if refund_cents <= 0:
            raise ValueError(f"refund amount must be positive for order_no={order_no}")

        refund = await self.stripe.Refund.create_async(
            payment_intent=intent_id,
            amount=refund_cents,
            reason="requested_by_customer",
            metadata={"order_no": order_no, "reason": (reason or "")[:500]},
        )

        refunded_at = _utcnow()
        blob["status"] = "refunded"
        blob["refunded_at"] = refunded_at.isoformat()
        blob["refund_amount_cents"] = refund_cents
        blob["refund_trade_no"] = refund.id
        if reason:
            blob["refund_reason"] = reason[:500]
        extra["payment"] = blob
        order.extra = json.dumps(extra, ensure_ascii=False)

        self.db_add_status_history(
            db,
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            source="payment",
            note=f"payment: stripe refunded trade_no={intent_id} refund={refund.id}",
        )
        await record_audit(
            db,
            actor_type="system",
            actor_id=0,
            action="payment.refund",
            target_type="order",
            target_id=order.id,
            payload={
                "order_no": order_no,
                "trade_no": intent_id,
                "refund_trade_no": refund.id,
                "refund_amount_cents": refund_cents,
                "provider": "stripe",
            },
        )
        from app.core.ds160 import revoke_order_ds160
        if revoke_order_ds160(order):
            await record_audit(
                db,
                actor_type="system",
                actor_id=0,
                action="ds160.code.revoked_on_refund",
                target_type="order",
                target_id=order.id,
                payload={"order_no": order_no, "provider": "stripe"},
            )
        await db.commit()
        await db.refresh(order)
        _log.info(
            "stripe payment refunded order_no={} refund_id={} cents={}",
            order_no,
            refund.id,
            refund_cents,
        )

        return OrderPaymentStatus(
            order_no=order_no,
            trade_no=intent_id,
            status="refunded",
            paid_at=_parse_iso(blob.get("paid_at")),
            amount_cents=int(blob.get("amount_cents") or 0),
            currency=blob.get("currency") or "USD",
            raw=blob,
        )

    # ------------------------------------------------------------------ #
    # V2.1 真接 payout (stripe.Transfer.create_async) — Affiliate only    #
    # ------------------------------------------------------------------ #
    async def payout(
        self,
        *,
        partner_id: str,
        amount_cents: int,
        currency: str = "USD",
        period: str = "",
        partner_account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Issue a real Stripe Transfer to an affiliate partner.

        V2.1-only — affiliates don't exist in V2. The affiliate service
        resolves `partner_account_id` from its own table; we accept it
        as a param so this method stays decoupled from the affiliate
        schema. If `partner_account_id` is omitted, we fall back to
        `settings.stripe_payout_account_id` (the platform's default
        Connect account).

        Returns a normalised result:
            {
                "transfer_id": "tr_...",
                "amount_cents": int,
                "currency": "usd",
                "status": "pending" | "paid" | "failed",
                "raw": {... full Stripe Transfer object ...},
            }

        Idempotency: pass `metadata={"period": "..."}` so a retried
        payout (same period for same partner) is detectable in the
        Stripe dashboard.
        """
        self._require_stripe()
        if amount_cents <= 0:
            raise ValueError(f"amount_cents must be positive, got {amount_cents}")
        destination = partner_account_id or self.payout_account_id
        if not destination:
            raise ValueError(
                "payout() requires partner_account_id (or "
                "STRIPE_PAYOUT_ACCOUNT_ID in .env)"
            )

        transfer = await self.stripe.Transfer.create_async(
            amount=int(amount_cents),
            currency=currency.lower(),
            destination=destination,
            description=f"Visa MVP affiliate payout partner={partner_id}",
            metadata={
                "partner_id": str(partner_id),
                "period": period or "",
                "source": "visa-mvp-v2.1-affiliate",
            },
        )
        _log.info(
            "stripe payout partner_id={} amount_cents={} currency={} "
            "transfer_id={}",
            partner_id, amount_cents, currency, transfer.id,
        )
        return {
            "transfer_id": transfer.id,
            "amount_cents": int(amount_cents),
            "currency": currency.lower(),
            "status": "paid" if getattr(transfer, "amount_reversed", 0) == 0
                       else "reversed",
            "raw": transfer.to_dict_recursive()
                   if hasattr(transfer, "to_dict_recursive")
                   else {"id": transfer.id},
        }


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _parse_iso(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        # Accept both "2026-06-12T08:30:00" and "...+00:00" forms.
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None


__all__ = [
    "PaymentProvider",
    "StripePaymentProvider",
    "CreateOrderResult",
    "OrderPaymentStatus",
    "get_payment_provider",
    "reset_payment_provider_for_tests",
]


# --------------------------------------------------------------------------- #
# V2.1 TODO — replace Mock with real channel                                   #
# --------------------------------------------------------------------------- #
# When the product team signs off on real payments (Mavis 10:54 picked
# "支付全 Mock, 后期 V2.1 阶段再接" → Stripe OR WeChat Pay), the swap is:
#
#   1. Add a `WeChatPayAdapter` (or `StripeAdapter`) under
#      `app/services/payment/adapter.py` implementing the same
#      `PaymentAdapter.create / confirm / query` contract.
#   2. Channel-select via `Settings.payment_channel: Literal["mock",
#      "wechatpay", "stripe"]` (zero credentials in `dev`).
#   3. The facade (`PaymentProvider` in this file) stays unchanged:
#      it already speaks in order_no / amount_cents / status, which is
#      exactly what the API + audit + E2E tests need. Only `_auto_notify`
#      and the auto-callback URL in `/api/v2/payment/notify` swap over
#      to the real signature-verified flow.
#
# Until then, no PAYMENT_* / WECHATPAY_* / STRIPE_* env vars exist, and
# this provider can be exercised end-to-end with `pytest` + curl alone.