"""/api/v2/affiliate/* — B-W8-4 standalone Affiliate endpoints (V2 §4.7, Mock-only).

Endpoints (5):
  - POST /api/v2/affiliate/track                       (JWT)  record a click
  - POST /api/v2/affiliate/attribute                   (JWT)  bind order → click
  - GET  /api/v2/affiliate/commission/{order_id}       (JWT)  compute commission
  - POST /api/v2/affiliate/payout                      (JWT)  settle partner
  - GET  /api/v2/affiliate/{partner_id}/stats          (PARTNER KEY) per-partner rollup

Auth model (per the V2 §4.7 spec):
  - The first 4 endpoints are *admin / OMS* actions: which user clicks
    a partner link?  Which user creates the order?  Both are users with
    a JWT. We authenticate with the standard `Authorization: Bearer
    <jwt>` (resolves to a real `User` row).
  - The 5th endpoint (`/{partner_id}/stats`) is the *partner-facing*
    surface: an external partner (e.g. a travel agency running a link
    campaign) polls it to see how many clicks / attributed orders /
    paid commission they have. We authenticate with a shared secret
    header `X-Partner-Key` — in V2 mock this is the same env-var the
    internal scheduler uses (`SYSTEM_API_KEY`), since we have no
    real partner onboarding. V2.1 will add per-partner API keys.

Why a standalone set?
  - The OMS / order service does not yet call `attribute()` — that's a
    Story for W9+ when order creation grows an `aff_code` field.
  - For V2, the dev console and E2E tests drive the full lifecycle via
    these 5 endpoints, mirroring the W6-1 SMS pattern.
  - V2.1 swap (CJ / ShareASale / impact.com) is a one-line change in
    `services/affiliate_provider.py::get_affiliate_provider`.
"""
from __future__ import annotations

import secrets
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.affiliate import (
    AttributeData,
    AttributeRequest,
    CommissionData,
    PayoutData,
    PayoutRequest,
    PartnerStatsData,
    TrackData,
    TrackRequest,
)
from app.schemas.common import ApiResponse
from app.services.affiliate_provider import (
    InvalidPayoutPeriod,
    MockAffiliateProvider,
    PayoutBelowFloor,
    UnknownClick,
    UnknownOrder,
    get_affiliate_provider,
)


router = APIRouter()
_log = get_logger()


# --------------------------------------------------------------------------- #
# Partner-key auth dependency (V2.1 will become per-partner keys)             #
# --------------------------------------------------------------------------- #
async def require_partner_key(
    x_partner_key: Annotated[
        Optional[str],
        Header(
            alias="X-Partner-Key",
            description=(
                "Shared partner secret. In V2 mock this is the same value as "
                "SYSTEM_API_KEY (no real partner onboarding). V2.1 will issue "
                "a per-partner key."
            ),
        ),
    ] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """Verify the `X-Partner-Key` header matches the configured secret.

    Returns 401 UNAUTHORIZED (code 1005) on:
      - missing header
      - value mismatch
    """
    if not x_partner_key:
        raise BizException(
            ErrorCode.UNAUTHORIZED,
            message="Missing X-Partner-Key header",
            data={"hint": "partner endpoint, requires partner API key"},
        )
    if not secrets.compare_digest(x_partner_key, settings.system_api_key):
        raise BizException(
            ErrorCode.UNAUTHORIZED,
            message="Invalid X-Partner-Key",
            data={},
        )


def _provider() -> MockAffiliateProvider:
    """Type-narrow the singleton to MockAffiliateProvider for the V2 mock.

    V2.1 swap: the factory will return CJ/ShareASale implementations
    that may not support `stats()`. The /stats endpoint will need to
    be re-evaluated then.
    """
    p = get_affiliate_provider()
    if not isinstance(p, MockAffiliateProvider):
        # V2.1 path — the real provider will be wired through a
        # thin ORM-backed stats endpoint, not in-memory.
        raise BizException(ErrorCode.NOT_FOUND, message="endpoint mock-only in V2")
    return p


# --------------------------------------------------------------------------- #
# 1. POST /api/v2/affiliate/track                                             #
# --------------------------------------------------------------------------- #
@router.post(
    "/track",
    response_model=ApiResponse[TrackData],
    summary="Record a click on an affiliate link (mock: in-memory dedup)",
)
async def track_click(
    body: TrackRequest,
    _user: User = Depends(get_current_user),
) -> ApiResponse[TrackData]:
    """V2 mock: every call lands in an in-memory store, dedup by click_id."""
    provider = _provider()
    result = await provider.track(
        aff_code=body.aff_code,
        click_id=body.click_id,
        landing_path=body.landing_path,
    )
    if not result.get("ok"):
        raise BizException(ErrorCode.INVALID_PARAMS, message=result.get("error") or "track failed")
    _log.info(
        "affiliate track HTTP aff_code={} click_id={} user_id={}",
        result["aff_code"], result["click_id"], _user.id,
    )
    return ApiResponse[TrackData](
        code="1000",
        message="OK",
        data=TrackData(
            click_id=result["click_id"],
            aff_code=result["aff_code"],
            partner_id=result["partner_id"],
            tracked_at=result["tracked_at"],
        ),
    )


# --------------------------------------------------------------------------- #
# 2. POST /api/v2/affiliate/attribute                                         #
# --------------------------------------------------------------------------- #
@router.post(
    "/attribute",
    response_model=ApiResponse[AttributeData],
    summary="Bind an order to a click (mock: in-memory map)",
)
async def attribute_order(
    body: AttributeRequest,
    _user: User = Depends(get_current_user),
) -> ApiResponse[AttributeData]:
    """V2 mock: look up the click and write an order_id → partner map."""
    provider = _provider()
    try:
        result = await provider.attribute(order_id=body.order_id, click_id=body.click_id)
    except UnknownClick as exc:
        # The click_id was never tracked. Surface as 4004 (closest V2
        # code for "resource missing" — affiliate doesn't have its own
        # code in the registry, and reusing NOT_FOUND is clean enough
        # since the partner-side root cause is "no such click").
        raise BizException(ErrorCode.NOT_FOUND, message=str(exc)) from exc
    if not result.get("ok"):
        raise BizException(ErrorCode.INVALID_PARAMS, message=result.get("error") or "attribute failed")
    _log.info(
        "affiliate attribute HTTP order_id={} click_id={} partner_id={} user_id={}",
        result["order_id"], result["click_id"], result["partner_id"], _user.id,
    )
    return ApiResponse[AttributeData](
        code="1000",
        message="OK",
        data=AttributeData(
            order_id=result["order_id"],
            click_id=result["click_id"],
            aff_code=result["aff_code"],
            partner_id=result["partner_id"],
            attributed=result["attributed"],
            attributed_at=result["attributed_at"],
        ),
    )


# --------------------------------------------------------------------------- #
# 3. GET /api/v2/affiliate/commission/{order_id}                              #
# --------------------------------------------------------------------------- #
@router.get(
    "/commission/{order_id}",
    response_model=ApiResponse[CommissionData],
    summary="Compute (or look up) commission for an attributed order (5% in V2 mock)",
)
async def get_commission(
    order_id: str = Path(..., min_length=4, max_length=64),
    order_total_cents: Optional[int] = None,
    _user: User = Depends(get_current_user),
) -> ApiResponse[CommissionData]:
    """V2 mock: 5% of `order_total_cents` (defaults to whatever was set at
    attribute-time, which in V2 is 0 since the OMS doesn't yet write the
    total here — pass `?order_total_cents=...` to force a calculation)."""
    provider = _provider()
    try:
        result = await provider.commission(
            order_id=order_id,
            order_total_cents=order_total_cents,
        )
    except UnknownOrder as exc:
        raise BizException(ErrorCode.NOT_FOUND, message=str(exc)) from exc
    _log.info(
        "affiliate commission HTTP order_id={} cents={} partner_id={} user_id={}",
        result["order_id"], result["commission_amount_cents"], result["partner_id"], _user.id,
    )
    return ApiResponse[CommissionData](
        code="1000",
        message="OK",
        data=CommissionData(
            order_id=result["order_id"],
            commission_id=result["commission_id"],
            commission_amount_cents=result["commission_amount_cents"],
            commission_rate=result["commission_rate"],
            currency=result["currency"],
            partner_id=result["partner_id"],
            computed_at=result["computed_at"],
        ),
    )


# --------------------------------------------------------------------------- #
# 4. POST /api/v2/affiliate/payout                                            #
# --------------------------------------------------------------------------- #
@router.post(
    "/payout",
    response_model=ApiResponse[PayoutData],
    summary="Settle a partner's outstanding commission (V2 mock: 100% paid)",
)
async def settle_payout(
    body: PayoutRequest,
    _user: User = Depends(get_current_user),
) -> ApiResponse[PayoutData]:
    """V2 mock: walks all attributed-but-unpaid commission, sums them,
    marks each order_id as paid, and returns a `payout_id` + `status=paid`."""
    provider = _provider()
    try:
        result = await provider.payout(partner_id=body.partner_id, period=body.period)
    except InvalidPayoutPeriod as exc:
        raise BizException(ErrorCode.INVALID_PARAMS, message=str(exc)) from exc
    except UnknownOrder as exc:
        raise BizException(ErrorCode.NOT_FOUND, message=str(exc)) from exc
    except PayoutBelowFloor as exc:
        raise BizException(ErrorCode.INVALID_PARAMS, message=str(exc)) from exc
    if not result.get("ok"):
        raise BizException(ErrorCode.INVALID_PARAMS, message=result.get("error") or "payout failed")
    _log.info(
        "affiliate payout HTTP payout_id={} partner_id={} period={} total_cents={} user_id={}",
        result["payout_id"], result["partner_id"], result["period"],
        result["total_amount_cents"], _user.id,
    )
    return ApiResponse[PayoutData](
        code="1000",
        message="OK",
        data=PayoutData(
            payout_id=result["payout_id"],
            partner_id=result["partner_id"],
            period=result["period"],
            order_ids=result["order_ids"],
            total_amount_cents=result["total_amount_cents"],
            currency=result["currency"],
            status=result["status"],
            paid_at=result["paid_at"],
        ),
    )


# --------------------------------------------------------------------------- #
# 5. GET /api/v2/affiliate/{partner_id}/stats                                 #
# --------------------------------------------------------------------------- #
@router.get(
    "/{partner_id}/stats",
    response_model=ApiResponse[PartnerStatsData],
    summary="Per-partner rollup (clicks / attributed orders / commission / paid). X-Partner-Key auth.",
)
async def partner_stats(
    partner_id: str = Path(..., min_length=4, max_length=64),
    _key: Annotated[None, Depends(require_partner_key)] = None,
) -> ApiResponse[PartnerStatsData]:
    """Partner-facing rollup. Auth: `X-Partner-Key` header."""
    provider = _provider()
    result = provider.stats(partner_id=partner_id)
    return ApiResponse[PartnerStatsData](code="1000", message="OK", data=PartnerStatsData(**result))
