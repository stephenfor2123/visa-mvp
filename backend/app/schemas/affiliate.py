"""Affiliate provider DTOs (B-W8-4) — V2 §4.7 standalone affiliate service.

Lives separately from any auth/order DTO so the standalone
`/api/v2/affiliate/*` routes don't drag in order-creation shapes.

Locked contract (see pm/wbs/B-W8-4.md):
  - 5 endpoints: track / attribute / commission / payout / stats
  - All 5 are mock-only in V2 (no real affiliate network integration)
  - Commission rate is hard-coded to 5% in V2 (V2.1 will read from a rule row)
"""
from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_VALID_PERIODS = ("daily", "weekly", "monthly")

# aff_code: 4-32 chars, alphanumeric + dash/underscore. (Real affiliate
# networks vary, e.g. CJ uses any string up to 50 chars; this is a
# sensible V2 mock cap that covers the common cases.)
_AFF_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{4,32}$")

# click_id is a UUID-ish / opaque string; we let the provider mint one if
# the caller doesn't supply it. 4-64 chars to keep the URL sane.
_CLICK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")

# order_id matches the V2 OMS format: ORD-XXXX or similar. We allow
# 4-64 chars to also accept v2.1 UUIDs without a rewrite.
_ORDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


# --------------------------------------------------------------------------- #
# Requests                                                                    #
# --------------------------------------------------------------------------- #
class TrackRequest(BaseModel):
    """POST /api/v2/affiliate/track — record a click on an affiliate link."""

    model_config = ConfigDict(extra="forbid")

    aff_code: str = Field(..., description="Partner code visible in the URL, e.g. 'AFF123'")
    click_id: Optional[str] = Field(None, description="Client-supplied click id; auto-minted if absent")
    landing_path: str = Field("/", description="Where the click landed on our site")

    @field_validator("aff_code")
    @classmethod
    def _v_aff_code(cls, v: str) -> str:
        v = v.strip()
        if not _AFF_CODE_RE.match(v):
            raise ValueError("aff_code must be 4-32 chars of [A-Za-z0-9_-]")
        return v

    @field_validator("click_id")
    @classmethod
    def _v_click_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not _CLICK_ID_RE.match(v):
            raise ValueError("click_id must be 4-64 chars of [A-Za-z0-9_-]")
        return v

    @field_validator("landing_path")
    @classmethod
    def _v_path(cls, v: str) -> str:
        if not v:
            return "/"
        if not (v.startswith("/") or v.startswith("http")):
            return "/" + v
        return v


class AttributeRequest(BaseModel):
    """POST /api/v2/affiliate/attribute — bind an order to a click."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(..., description="Order to attribute, e.g. 'ORD-12345'")
    click_id: str = Field(..., description="The click_id returned by an earlier /track call")

    @field_validator("order_id")
    @classmethod
    def _v_order_id(cls, v: str) -> str:
        v = v.strip()
        if not _ORDER_ID_RE.match(v):
            raise ValueError("order_id must be 4-64 chars of [A-Za-z0-9_-]")
        return v

    @field_validator("click_id")
    @classmethod
    def _v_click_id(cls, v: str) -> str:
        v = v.strip()
        if not _CLICK_ID_RE.match(v):
            raise ValueError("click_id must be 4-64 chars of [A-Za-z0-9_-]")
        return v


class CommissionQueryRequest(BaseModel):
    """GET /api/v2/affiliate/commission/{order_id} — query commission.

    `order_total_cents` is an OPTIONAL query param: pass it when the order
    was attributed but the order service didn't yet write the total. In
    V2 mock, the total is held in-memory so most calls won't need it.
    """

    order_id: str = Field(..., description="Order to compute commission for")
    order_total_cents: Optional[int] = Field(
        None, ge=1, le=10_000_000,
        description="Order total in cents; if absent, the stored total is used",
    )

    @field_validator("order_id")
    @classmethod
    def _v_order_id(cls, v: str) -> str:
        v = v.strip()
        if not _ORDER_ID_RE.match(v):
            raise ValueError("order_id must be 4-64 chars of [A-Za-z0-9_-]")
        return v


class PayoutRequest(BaseModel):
    """POST /api/v2/affiliate/payout — settle a partner's outstanding commission."""

    model_config = ConfigDict(extra="forbid")

    partner_id: str = Field(..., min_length=4, max_length=64)
    period: str = Field(..., description="daily / weekly / monthly")

    @field_validator("partner_id")
    @classmethod
    def _v_partner_id(cls, v: str) -> str:
        v = v.strip()
        if not _AFF_CODE_RE.match(v):
            raise ValueError("partner_id must be 4-32 chars of [A-Za-z0-9_-]")
        return v

    @field_validator("period")
    @classmethod
    def _v_period(cls, v: str) -> str:
        if v not in _VALID_PERIODS:
            raise ValueError(f"period must be one of {list(_VALID_PERIODS)}")
        return v


# --------------------------------------------------------------------------- #
# Responses                                                                   #
# --------------------------------------------------------------------------- #
class TrackData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    click_id: str
    aff_code: str
    partner_id: str
    tracked_at: str


class AttributeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    click_id: str
    aff_code: str
    partner_id: str
    attributed: bool
    attributed_at: str


class CommissionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    commission_id: str
    commission_amount_cents: int
    commission_rate: str = Field(..., description="Decimal-string, e.g. '0.05' for 5%")
    currency: str
    partner_id: str
    computed_at: str


class PayoutData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payout_id: str
    partner_id: str
    period: str
    order_ids: List[str]
    total_amount_cents: int
    currency: str
    status: str = Field(..., description="paid in V2 mock; V2.1 will add 'pending' / 'failed'")
    paid_at: str


class PartnerStatsData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partner_id: str
    click_count: int
    attributed_count: int
    commission_cents: int
    paid_cents: int
    pending_cents: int
    currency: str
    orders: List[str]
    payouts: List[str]
