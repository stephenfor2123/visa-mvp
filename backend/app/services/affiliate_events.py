"""B-W9-3 — OMS event hooks for AffiliateProvider (V2 §4.7).

Why a dedicated events module (vs. calling the provider inline from
order_service):

  - The Affiliate provider is intentionally decoupled from the OMS
    (see B-W8-4 `affiliate_provider.py` module docstring). It exposes
    four pure async methods on a singleton — no DB writes, no row
    joins. Inlining those calls in `order_service.py` would couple
    the order state-machine to the affiliate state machine, which we
    want to swap (mock → CJ/ShareASale/impact.com) without touching
    the OMS.

  - This module is the seam. `order_service.create()` calls
    `on_order_created(order)`, `payment_provider.handle_notify()`
    calls `on_payment_completed(order)`, and `order_service.cancel()`
    / future refund flow calls `on_order_rejected(order)`.

Hook semantics:

  - `on_order_created(order)` — fires AFTER the order row is committed.
    If `order.aff_code` is set:
      1) `track(aff_code, click_id=...)` so a fresh click_id is
         available (idempotent if already tracked).
      2) `attribute(order_id, click_id)` binds the order to the
         click — also idempotent.
    If `aff_code` is None we no-op (most orders come direct).

  - `on_payment_completed(order)` — fires AFTER `payment.notify`
    flips status → `paid`. We call `commission(order_id,
    order_total_cents)` using the order's `total_amount` (converted
    to cents). Idempotent: re-call returns the same commission record.

  - `on_order_rejected(order)` — fires on cancel / refund. V2 mock
    has no reverse-commission primitive (the partner has not been paid
    yet at cancel-time, so there's nothing to claw back). We log the
    event so the audit trail shows "affiliate refund was signalled",
    and any V2.1 real provider that exposes a `reverse()` primitive
    can be wired here without an OMS change.

All hooks are best-effort: any error inside the affiliate provider
MUST NOT fail the parent transaction. We catch `Exception` and log,
then continue — the user-visible order still succeeds even if the
affiliate side hiccups. This matches the W8-4 contract (provider is
mock + in-memory, can't realistically throw, but we still defend the
boundary).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from loguru import logger

from app.models.order import Order
from app.services.affiliate_provider import (
    AffiliateProviderError,
    UnknownClick,
    UnknownOrder,
    get_affiliate_provider,
)


_log = logger.bind(component="affiliate_events")


def _provider():
    """Lazy singleton accessor — the events fire after `await get_db()`,
    so we re-fetch the provider each time. `get_affiliate_provider` is
    cached but cheap (single Lock + dict lookup)."""
    return get_affiliate_provider()


def _decimal_to_cents(amount: Decimal | float | int | None) -> int:
    """Convert the order's `total_amount` (Decimal dollars) to integer cents.

    V2 mock: orders are always priced in whole dollars in the test seed
    data, so this never loses precision. V2.1 with real pricing should
    round HALF_UP to be consistent with the commission rounding rule.
    """
    if amount is None:
        return 0
    if isinstance(amount, Decimal):
        cents = (amount * Decimal("100")).quantize(Decimal("1"))
        return int(cents)
    return int(round(float(amount) * 100))


# --------------------------------------------------------------------------- #
# 1. on_order_created                                                          #
# --------------------------------------------------------------------------- #
async def on_order_created(
    order: Order, *, click_id: Optional[str] = None
) -> dict:
    """Bind a freshly-created order to the affiliate click for its `aff_code`.

    Args:
        order: The persisted Order row (must have `id` + `order_no`).
        click_id: Optional pre-tracked click_id (caller has already run
            `track()`). If absent, we look up the latest tracked click
            for `order.aff_code` via `attribute()` — the V2 mock provider
            is single-shot per click, so this is a "first click wins"
            model. If the partner has no clicks on file we no-op and log.

    Returns:
        A small dict the caller can log:
            {
              "ok": bool,
              "order_id": str,
              "aff_code": str | None,
              "click_id": str | None,
              "partner_id": str | None,
              "skipped_reason": str | None,
            }

        The order row is NOT mutated here — `aff_code` was already
        persisted by `order_service.create()` before this hook fires.
    """
    if not order.aff_code:
        _log.info(
            "affiliate on_order_created skip order_no={} reason=no_aff_code",
            order.order_no,
        )
        return {
            "ok": True,
            "order_id": order.order_no,
            "aff_code": None,
            "click_id": None,
            "partner_id": None,
            "skipped_reason": "no_aff_code",
        }

    provider = _provider()
    try:
        # Step 1 — make sure a click is on file for this aff_code.
        # If the caller already supplied a click_id, `track()` dedups
        # by click_id and is a no-op. Otherwise we mint a fresh one
        # and the V2 mock attributes to it.
        if click_id is None:
            click_id = f"oms_click_{order.order_no}"
        track_result = await provider.track(
            aff_code=order.aff_code, click_id=click_id
        )
        if not track_result.get("ok"):
            _log.warning(
                "affiliate track failed order_no={} aff_code={} err={}",
                order.order_no,
                order.aff_code,
                track_result.get("error"),
            )
            return {
                "ok": False,
                "order_id": order.order_no,
                "aff_code": order.aff_code,
                "click_id": None,
                "partner_id": None,
                "skipped_reason": f"track_failed: {track_result.get('error')}",
            }
        resolved_click_id = track_result["click_id"]

        # Step 2 — attribute the order to that click.
        attr_result = await provider.attribute(
            order_id=order.order_no, click_id=resolved_click_id
        )
        _log.info(
            "affiliate on_order_created OK order_no={} aff_code={} partner_id={} click_id={}",
            order.order_no,
            order.aff_code,
            attr_result.get("partner_id"),
            resolved_click_id,
        )
        return {
            "ok": True,
            "order_id": order.order_no,
            "aff_code": order.aff_code,
            "click_id": resolved_click_id,
            "partner_id": attr_result.get("partner_id"),
            "skipped_reason": None,
        }
    except AffiliateProviderError as exc:
        _log.warning(
            "affiliate on_order_created provider_error order_no={} aff_code={} err={}",
            order.order_no, order.aff_code, exc,
        )
        return {
            "ok": False,
            "order_id": order.order_no,
            "aff_code": order.aff_code,
            "click_id": None,
            "partner_id": None,
            "skipped_reason": f"provider_error: {exc}",
        }
    except Exception as exc:  # noqa: BLE001 — defensive boundary
        # Best-effort: never let an affiliate glitch fail the OMS write.
        _log.exception(
            "affiliate on_order_created unexpected_error order_no={} aff_code={}",
            order.order_no, order.aff_code,
        )
        return {
            "ok": False,
            "order_id": order.order_no,
            "aff_code": order.aff_code,
            "click_id": None,
            "partner_id": None,
            "skipped_reason": f"unexpected: {exc}",
        }


# --------------------------------------------------------------------------- #
# 2. on_payment_completed                                                      #
# --------------------------------------------------------------------------- #
async def on_payment_completed(order: Order) -> dict:
    """Compute (and stamp) the partner commission for a paid order.

    Called from `payment_provider.handle_notify()` once the payment
    status flips to `paid`. We pass `order_total_cents` derived from
    `order.total_amount` so the commission rule (5% in V2 mock) has a
    number to multiply against. The attribution MUST have already run
    via `on_order_created` — otherwise the provider raises UnknownOrder
    and we surface that as `skipped_reason="not_attributed"`.

    Idempotency: re-calling this hook (e.g. on a duplicate payment
    webhook) returns the same commission_amount without recomputing
    — the provider dedups on `order_id`.

    Returns:
        {
          "ok": bool,
          "order_id": str,
          "commission_amount_cents": int | None,
          "partner_id": str | None,
          "skipped_reason": str | None,
        }
    """
    provider = _provider()
    order_total_cents = _decimal_to_cents(order.total_amount)
    try:
        result = await provider.commission(
            order_id=order.order_no,
            order_total_cents=order_total_cents,
        )
        _log.info(
            "affiliate on_payment_completed OK order_no={} cents={} partner_id={}",
            order.order_no,
            result.get("commission_amount_cents"),
            result.get("partner_id"),
        )
        return {
            "ok": True,
            "order_id": order.order_no,
            "commission_amount_cents": result.get("commission_amount_cents"),
            "partner_id": result.get("partner_id"),
            "skipped_reason": None,
        }
    except UnknownOrder as exc:
        # Order has no attribution on file — most likely the OMS
        # created it without `aff_code`, so attribution was skipped.
        # Not an error — surface as skipped so callers can log it.
        _log.info(
            "affiliate on_payment_completed skip order_no={} reason=not_attributed err={}",
            order.order_no, exc,
        )
        return {
            "ok": True,
            "order_id": order.order_no,
            "commission_amount_cents": None,
            "partner_id": None,
            "skipped_reason": "not_attributed",
        }
    except AffiliateProviderError as exc:
        _log.warning(
            "affiliate on_payment_completed provider_error order_no={} err={}",
            order.order_no, exc,
        )
        return {
            "ok": False,
            "order_id": order.order_no,
            "commission_amount_cents": None,
            "partner_id": None,
            "skipped_reason": f"provider_error: {exc}",
        }
    except Exception as exc:  # noqa: BLE001 — defensive boundary
        _log.exception(
            "affiliate on_payment_completed unexpected_error order_no={}",
            order.order_no,
        )
        return {
            "ok": False,
            "order_id": order.order_no,
            "commission_amount_cents": None,
            "partner_id": None,
            "skipped_reason": f"unexpected: {exc}",
        }


# --------------------------------------------------------------------------- #
# 3. on_order_rejected                                                         #
# --------------------------------------------------------------------------- #
async def on_order_rejected(order: Order) -> dict:
    """Signal that an order has been cancelled / refunded.

    V2 mock: the partner has not been paid yet (payouts settle only
    via `/api/v2/affiliate/payout`), so a cancel/refund has nothing
    to claw back at the commission level. We log the signal so the
    audit trail records that the affiliate side was notified — V2.1
    real providers (CJ, ShareASale) will plug a `reverse()` call here
    once their SDK exposes one.

    Returns:
        {
          "ok": True,
          "order_id": str,
          "action": "logged_only" | "reversed",
          "skipped_reason": str | None,
        }
    """
    _log.info(
        "affiliate on_order_rejected signal order_no={} status={} aff_code={} (mock: logged-only, no reverse API in V2)",
        order.order_no, order.status, order.aff_code,
    )
    return {
        "ok": True,
        "order_id": order.order_no,
        "action": "logged_only",
        "skipped_reason": None,
    }


__all__ = [
    "on_order_created",
    "on_payment_completed",
    "on_order_rejected",
]