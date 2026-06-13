"""B-W8-4 — Standalone Affiliate provider (V2 §4.7, Mock-only for V2).

Scope:
  - `AffiliateProvider` ABC (4 methods: track / attribute / commission / payout)
  - `MockAffiliateProvider` — the only implementation in V2. No CJ Affiliate,
    no ShareASale, no impact.com SDK is wired in V2; that lands in V2.1 once
    we have partner sign-ups to actually pay.
  - In-memory store of: clicks (aff_code, click_id) → partner_id, and
    orders (order_id) → (partner_id, commission_amount).
  - Zero credentials: no AFFILIATE_* env vars, no partner onboarding,
    no real-money payout.

Coexistence with future OMS / Order service:
  - The W4 / W6 order service does NOT yet call `attribute()` — that's a
    Story for W9+ (the order creation flow needs an affiliate attribution
    slot in the request body, which V2 doesn't carry).
  - For V2, callers explicitly invoke the `/api/v2/affiliate/*` endpoints
    so the dev console / E2E tests can drive a full lifecycle.
  - In V2.1, the order service will call `provider.attribute(order_id,
    click_id)` on the `order.created` event; this module is that consumer.

Commission rules (V2 mock, hard-coded — V2.1 will read from a DB rule row):
  - rate = 5% of order total
  - currency = "USD" (mock — V2.1 will mirror the order's currency)
  - attribution window = 30 days (mock: not enforced, V2.1 will store a
    click timestamp and reject attribute calls older than 30d)

Payout rules:
  - period ∈ {"daily", "weekly", "monthly"} — V2 accepts all, mock always
    succeeds and stamps `status="paid"`.
  - payout_id is deterministically `mock_payout_<partner_id>_<period>_<ts>`.
"""
from __future__ import annotations

import secrets
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from loguru import logger


_log = logger.bind(component="affiliate_provider")


# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #
VALID_PERIODS = ("daily", "weekly", "monthly")
DEFAULT_COMMISSION_RATE = Decimal("0.05")          # 5%
DEFAULT_CURRENCY = "USD"
MIN_PAYOUT_AMOUNT_CENTS = 100                     # $1.00 floor — mock


# --------------------------------------------------------------------------- #
# Errors                                                                      #
# --------------------------------------------------------------------------- #
class AffiliateProviderError(Exception):
    """Base for provider-level errors."""


class UnknownClick(AffiliateProviderError):
    """track() / attribute() called with a click_id that was never tracked."""


class UnknownOrder(AffiliateProviderError):
    """commission() / payout() called with an order_id / partner_id that
    has no attribution record."""


class InvalidPayoutPeriod(AffiliateProviderError):
    """payout() period is not in VALID_PERIODS."""


class PayoutBelowFloor(AffiliateProviderError):
    """Computed payout total is below the configured floor — refuse to pay."""


# --------------------------------------------------------------------------- #
# Data classes — internal in-memory state                                      #
# --------------------------------------------------------------------------- #
@dataclass
class _Click:
    click_id: str
    aff_code: str
    partner_id: str
    tracked_at: datetime
    landing_path: str = "/"


@dataclass
class _Attribution:
    order_id: str
    click_id: str
    aff_code: str
    partner_id: str
    order_total_cents: int
    commission_rate: Decimal
    commission_cents: int
    currency: str
    attributed_at: datetime


@dataclass
class _Payout:
    payout_id: str
    partner_id: str
    period: str
    order_ids: list[str]
    total_amount_cents: int
    currency: str
    status: str               # "paid" in mock
    paid_at: datetime


@dataclass
class _PartnerAggregate:
    """Per-partner rollup, computed on demand in `stats()`."""

    partner_id: str
    click_count: int = 0
    attributed_count: int = 0
    commission_cents: int = 0
    payout_cents: int = 0
    orders: list[str] = field(default_factory=list)
    pays: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Abstract base                                                              #
# --------------------------------------------------------------------------- #
class AffiliateProvider(ABC):
    """Affiliate tracking + attribution + commission + payout (V2 §4.7).

    Lifecycle (mock or real):
        1. partner's user clicks https://visago.com/?aff=AFF123
            → track(aff_code, click_id) returns a click_id we echo back
        2. the user lands and signs up / makes an order
            → attribute(order_id, click_id) binds the order to the partner
        3. the order is paid / completed
            → commission(order_id) returns the partner's share (5% in V2)
        4. the partner requests a settlement
            → payout(partner_id, period) returns a payout record

    All four methods MUST be idempotent enough for at-least-once callers:
    - `track()` — the same (aff_code, click_id) re-tracked should return
      the SAME click_id, not a new one.
    - `attribute()` — re-attribute the same (order_id, click_id) is a no-op.
    - `commission()` — purely read; can be called many times.
    - `payout()` — must NOT double-pay; a partner who already settled the
      same period should be told "already paid" not silently re-paid.
    """

    @abstractmethod
    async def track(self, aff_code: str, click_id: Optional[str] = None, landing_path: str = "/") -> dict:
        """Record a click on an affiliate link.

        Args:
            aff_code: The partner code visible in the URL (e.g. 'AFF123').
            click_id: Client-supplied click id (UUID4 typical). If absent
                the provider mints one. Re-using an existing click_id
                is a no-op (idempotency).
            landing_path: Where the click landed on our site. Persisted
                for analytics; V2.1 will use it to compute conversion rate.

        Returns:
            {
                "ok": True,
                "click_id": str,
                "aff_code": str,
                "partner_id": str,   # derived from aff_code (mock: 'PARTNER_<code>')
                "tracked_at": iso-timestamp,
            }
        """
        raise NotImplementedError

    @abstractmethod
    async def attribute(self, order_id: str, click_id: str) -> dict:
        """Bind an order to the click that drove it.

        Args:
            order_id: The order the user just created (V2: any string we
                can echo back; V2.1: a real order_no from the OMS).
            click_id: The click_id returned by an earlier `track()` call.

        Returns:
            {
                "ok": True,
                "order_id": str,
                "click_id": str,
                "aff_code": str,
                "partner_id": str,
                "attributed": True,
                "attributed_at": iso-timestamp,
            }

        Raises:
            UnknownClick: click_id was never tracked.
        """
        raise NotImplementedError

    @abstractmethod
    async def commission(self, order_id: str, order_total_cents: Optional[int] = None) -> dict:
        """Compute (or look up) the commission for an attributed order.

        Args:
            order_id: The attributed order.
            order_total_cents: If the order wasn't already attributed, this
                is a *fallback* used to compute a commission IF a click is
                on file for it. The common case is: call `attribute()`
                first with click_id, then call `commission()` with no
                `order_total_cents` and we use the stored total.

        Returns:
            {
                "ok": True,
                "order_id": str,
                "commission_id": str,         # mock: 'mock_comm_<ts>_<rand>'
                "commission_amount_cents": int,
                "commission_rate": "0.05",     # str to survive JSON Decimal
                "currency": "USD",
                "partner_id": str,
            }
        """
        raise NotImplementedError

    @abstractmethod
    async def payout(self, partner_id: str, period: str) -> dict:
        """Settle all attributed-but-unpaid commission for a partner.

        Args:
            partner_id: The partner to pay.
            period: 'daily' / 'weekly' / 'monthly'.

        Returns:
            {
                "ok": True,
                "payout_id": str,
                "partner_id": str,
                "period": str,
                "order_ids": [str, ...],
                "total_amount_cents": int,
                "currency": "USD",
                "status": "paid",         # mock always paid
                "paid_at": iso-timestamp,
            }

        Raises:
            UnknownOrder: partner has nothing to pay.
            InvalidPayoutPeriod: period not in VALID_PERIODS.
            PayoutBelowFloor: computed total < MIN_PAYOUT_AMOUNT_CENTS.
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mock implementation (V2 default)                                            #
# --------------------------------------------------------------------------- #
class MockAffiliateProvider(AffiliateProvider):
    """In-process mock. No external deps, no creds, no network.

    State held in three dicts (each protected by a `threading.Lock`):
      - `_clicks`     : click_id     -> _Click
      - `_attribs`    : order_id     -> _Attribution
      - `_payouts`    : payout_id    -> _Payout

    Aff_code → partner_id mapping is purely deterministic in V2 mock:
        partner_id = f"PARTNER_{aff_code.upper()}"
    In V2.1, this becomes a DB join against a `partners` table.
    """

    def __init__(
        self,
        commission_rate: Decimal = DEFAULT_COMMISSION_RATE,
        currency: str = DEFAULT_CURRENCY,
        min_payout_cents: int = MIN_PAYOUT_AMOUNT_CENTS,
    ) -> None:
        if not (0 < commission_rate < 1):
            raise ValueError("commission_rate must be in (0, 1)")
        if min_payout_cents < 0:
            raise ValueError("min_payout_cents must be >= 0")
        self._rate = commission_rate
        self._currency = currency
        self._min_payout = min_payout_cents

        self._clicks: dict[str, _Click] = {}
        self._attribs: dict[str, _Attribution] = {}
        self._payouts: dict[str, _Payout] = {}

        # Per-partner set of order_ids already included in a payout — used
        # to make payout() idempotent (don't re-pay an order).
        self._paid_orders: dict[str, set[str]] = {}

        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _partner_id_for(aff_code: str) -> str:
        return f"PARTNER_{aff_code.strip().upper()}"

    @staticmethod
    def _now_wall() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _gen_click_id(supplied: Optional[str]) -> str:
        if supplied:
            return supplied
        return f"mock_click_{int(time.time() * 1000)}_{secrets.token_hex(4)}"

    @staticmethod
    def _gen_commission_id() -> str:
        return f"mock_comm_{int(time.time() * 1000)}_{secrets.token_hex(4)}"

    @staticmethod
    def _gen_payout_id(partner_id: str, period: str) -> str:
        return f"mock_payout_{partner_id}_{period}_{int(time.time() * 1000)}_{secrets.token_hex(3)}"

    def _compute_commission_cents(self, order_total_cents: int) -> int:
        # Use Decimal for the rate multiplication, round HALF_UP to cents.
        amt = (Decimal(order_total_cents) * self._rate).quantize(Decimal("1"))
        return int(amt)

    # ------------------------------------------------------------------ #
    # 1. track                                                            #
    # ------------------------------------------------------------------ #
    async def track(
        self,
        aff_code: str,
        click_id: Optional[str] = None,
        landing_path: str = "/",
    ) -> dict:
        if not aff_code or not aff_code.strip():
            return {"ok": False, "error": "aff_code is required"}
        if not (landing_path.startswith("/") or landing_path.startswith("http")):
            landing_path = "/" + landing_path

        cid = self._gen_click_id(click_id)
        now = self._now_wall()
        partner_id = self._partner_id_for(aff_code)

        with self._lock:
            existing = self._clicks.get(cid)
            if existing is not None:
                # Idempotency: re-tracking the same click returns the
                # original record, not a new one.
                _log.info(
                    "affiliate track dedup click_id={} aff_code={} partner_id={}",
                    cid, existing.aff_code, existing.partner_id,
                )
                return {
                    "ok": True,
                    "click_id": cid,
                    "aff_code": existing.aff_code,
                    "partner_id": existing.partner_id,
                    "tracked_at": existing.tracked_at.isoformat(timespec="seconds"),
                }
            self._clicks[cid] = _Click(
                click_id=cid,
                aff_code=aff_code.strip(),
                partner_id=partner_id,
                tracked_at=now,
                landing_path=landing_path,
            )

        _log.info(
            "affiliate track OK aff_code={} click_id={} partner_id={} path={}",
            aff_code, cid, partner_id, landing_path,
        )
        return {
            "ok": True,
            "click_id": cid,
            "aff_code": aff_code.strip(),
            "partner_id": partner_id,
            "tracked_at": now.isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------ #
    # 2. attribute                                                        #
    # ------------------------------------------------------------------ #
    async def attribute(self, order_id: str, click_id: str) -> dict:
        if not order_id or not order_id.strip():
            return {"ok": False, "error": "order_id is required"}
        if not click_id or not click_id.strip():
            return {"ok": False, "error": "click_id is required"}

        order_id = order_id.strip()
        click_id = click_id.strip()

        with self._lock:
            click = self._clicks.get(click_id)
            if click is None:
                raise UnknownClick(f"click_id={click_id} was never tracked")

            existing = self._attribs.get(order_id)
            if existing is not None:
                # Idempotency: re-attribute the same order returns the
                # same record, regardless of what click_id the caller
                # passes (we trust the first call).
                _log.info(
                    "affiliate attribute dedup order_id={} click_id={} partner_id={}",
                    order_id, click_id, existing.partner_id,
                )
                return {
                    "ok": True,
                    "order_id": order_id,
                    "click_id": existing.click_id,
                    "aff_code": existing.aff_code,
                    "partner_id": existing.partner_id,
                    "attributed": True,
                    "attributed_at": existing.attributed_at.isoformat(timespec="seconds"),
                }

            now = self._now_wall()
            # commission_total is computed later (at commission() time)
            # because the order total may not be known at this point.
            self._attribs[order_id] = _Attribution(
                order_id=order_id,
                click_id=click_id,
                aff_code=click.aff_code,
                partner_id=click.partner_id,
                order_total_cents=0,        # not yet known
                commission_rate=self._rate,
                commission_cents=0,         # not yet known
                currency=self._currency,
                attributed_at=now,
            )

        _log.info(
            "affiliate attribute OK order_id={} click_id={} partner_id={}",
            order_id, click_id, click.partner_id,
        )
        return {
            "ok": True,
            "order_id": order_id,
            "click_id": click_id,
            "aff_code": click.aff_code,
            "partner_id": click.partner_id,
            "attributed": True,
            "attributed_at": now.isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------ #
    # 3. commission                                                       #
    # ------------------------------------------------------------------ #
    async def commission(self, order_id: str, order_total_cents: Optional[int] = None) -> dict:
        if not order_id or not order_id.strip():
            return {"ok": False, "error": "order_id is required"}

        order_id = order_id.strip()
        now = self._now_wall()

        with self._lock:
            attr = self._attribs.get(order_id)
            if attr is None:
                if order_total_cents is None:
                    raise UnknownOrder(
                        f"order_id={order_id} is not attributed and no order_total_cents supplied"
                    )
                # Caller supplied a total but no attribution. In V2 mock
                # we can't compute a commission without a partner; refuse
                # cleanly so the caller knows to call attribute() first.
                raise UnknownOrder(
                    f"order_id={order_id} has no click attribution; call attribute() first"
                )

            # If we know the order total, recompute the commission. If not,
            # return whatever we have (which is zero on a fresh attribute).
            if order_total_cents is not None and order_total_cents > 0:
                attr.order_total_cents = int(order_total_cents)
                attr.commission_cents = self._compute_commission_cents(int(order_total_cents))
            commission_cents = attr.commission_cents
            partner_id = attr.partner_id
            currency = attr.currency
            rate_str = str(attr.commission_rate)

        commission_id = self._gen_commission_id()
        _log.info(
            "affiliate commission OK order_id={} partner_id={} cents={} rate={}",
            order_id, partner_id, commission_cents, rate_str,
        )
        return {
            "ok": True,
            "order_id": order_id,
            "commission_id": commission_id,
            "commission_amount_cents": commission_cents,
            "commission_rate": rate_str,
            "currency": currency,
            "partner_id": partner_id,
            "computed_at": now.isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------ #
    # 4. payout                                                           #
    # ------------------------------------------------------------------ #
    async def payout(self, partner_id: str, period: str) -> dict:
        if period not in VALID_PERIODS:
            raise InvalidPayoutPeriod(f"period must be one of {list(VALID_PERIODS)}")
        if not partner_id or not partner_id.strip():
            return {"ok": False, "error": "partner_id is required"}
        partner_id = partner_id.strip()
        now = self._now_wall()

        with self._lock:
            paid_set = self._paid_orders.setdefault(partner_id, set())
            order_ids: list[str] = []
            total_cents = 0
            for order_id, attr in self._attribs.items():
                if attr.partner_id != partner_id:
                    continue
                if order_id in paid_set:
                    continue
                if attr.commission_cents <= 0:
                    continue
                order_ids.append(order_id)
                total_cents += attr.commission_cents

            if not order_ids:
                raise UnknownOrder(f"partner_id={partner_id} has nothing to pay")
            if total_cents < self._min_payout:
                raise PayoutBelowFloor(
                    f"payout total {total_cents}c is below floor {self._min_payout}c"
                )

            payout_id = self._gen_payout_id(partner_id, period)
            self._payouts[payout_id] = _Payout(
                payout_id=payout_id,
                partner_id=partner_id,
                period=period,
                order_ids=list(order_ids),
                total_amount_cents=total_cents,
                currency=self._currency,
                status="paid",
                paid_at=now,
            )
            paid_set.update(order_ids)

        _log.info(
            "affiliate payout OK payout_id={} partner_id={} period={} orders={} total_cents={}",
            payout_id, partner_id, period, len(order_ids), total_cents,
        )
        return {
            "ok": True,
            "payout_id": payout_id,
            "partner_id": partner_id,
            "period": period,
            "order_ids": order_ids,
            "total_amount_cents": total_cents,
            "currency": self._currency,
            "status": "paid",
            "paid_at": now.isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------ #
    # 5. stats (per partner rollup — used by /api/v2/affiliate/.../stats) #
    # ------------------------------------------------------------------ #
    def stats(self, partner_id: str) -> dict:
        """Per-partner rollup. Not on the ABC — V2 mock convenience for
        the /stats endpoint. Real CJ/ShareASale would compute this in SQL.

        Returns:
            {
                "partner_id": str,
                "click_count": int,
                "attributed_count": int,   # orders attributed to this partner
                "commission_cents": int,   # total commission across attributed orders
                "paid_cents": int,         # total settled via payout()
                "pending_cents": int,      # commission - paid
                "currency": "USD",
                "orders": [order_id, ...],
            }
        """
        agg = _PartnerAggregate(partner_id=partner_id)
        with self._lock:
            for click in self._clicks.values():
                if click.partner_id == partner_id:
                    agg.click_count += 1
            for order_id, attr in self._attribs.items():
                if attr.partner_id != partner_id:
                    continue
                agg.attributed_count += 1
                agg.commission_cents += attr.commission_cents
                agg.orders.append(order_id)
            for pay_id, pay in self._payouts.items():
                if pay.partner_id != partner_id:
                    continue
                agg.payout_cents += pay.total_amount_cents
                agg.pays.append(pay_id)
        return {
            "partner_id": partner_id,
            "click_count": agg.click_count,
            "attributed_count": agg.attributed_count,
            "commission_cents": agg.commission_cents,
            "paid_cents": agg.payout_cents,
            "pending_cents": max(0, agg.commission_cents - agg.payout_cents),
            "currency": self._currency,
            "orders": sorted(agg.orders),
            "payouts": sorted(agg.pays),
        }


# --------------------------------------------------------------------------- #
# Factory — single source of truth                                            #
# --------------------------------------------------------------------------- #
_provider_singleton: Optional[AffiliateProvider] = None
_provider_lock = threading.Lock()


def get_affiliate_provider() -> AffiliateProvider:
    """Return the process-wide MockAffiliateProvider (V2 default).

    V2.1 swap: read `settings.affiliate_provider_kind` ("mock" / "cj" /
    "shareasale") and instantiate the matching class. For V2 we hard-code
    mock to satisfy the "零凭据 / 1-2 天可跑" rule.
    """
    global _provider_singleton
    with _provider_lock:
        if _provider_singleton is None:
            _provider_singleton = MockAffiliateProvider()
        return _provider_singleton


def reset_affiliate_provider_for_tests() -> None:
    """Drop the singleton — used by pytest to start each test with a clean store."""
    global _provider_singleton
    with _provider_lock:
        _provider_singleton = None
