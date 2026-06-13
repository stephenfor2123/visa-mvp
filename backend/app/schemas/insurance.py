"""Insurance provider DTOs (B-W8-3) — V2 §4.6 拒签险 service.

Locked contract (see pm/wbs/B-W8-3.md + D spec):
  - 4 endpoints: POST /quote, POST /bind, POST /claim, GET /{policy_id}
  - All money in **cents** (integer), currency string separate
    (mock returns "CNY" — V2 §4.6 spec uses ¥ throughout).
  - All timestamps ISO8601 UTC with second precision.
  - `rejection_reason` is free text (consular 拒签信原文 or summary).
  - Mock always returns `claim.status = "approved"`.

Why we don't reuse `app.schemas.payment.*`: insurance quotes are
quote/bind/claim (3-stage), payment is create/notify/query/close (4-stage
linear) — different verbs, different response shapes.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# 2-letter ISO 3166-1 alpha-2 — we accept the 9 V2 destinations plus a
# wide fallback for "high-risk" countries. The mock decides the multiplier
# by membership in `LOW_RISK_COUNTRIES`; the DTO just enforces format.
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def _normalize_country(value: str) -> str:
    return value.strip().upper()


# --------------------------------------------------------------------------- #
# Requests                                                                    #
# --------------------------------------------------------------------------- #
class QuoteRequest(BaseModel):
    """Request body for POST /api/v2/insurance/quote."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(..., min_length=2, max_length=64, description="V2-YYYYMMDD-NNNNNN")
    applicant_age: int = Field(..., ge=0, le=120, description="0-120 inclusive")
    destination_country: str = Field(..., description="ISO 3166-1 alpha-2, e.g. 'US'")

    @field_validator("order_id")
    @classmethod
    def _v_order_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("order_id cannot be empty")
        return cleaned

    @field_validator("destination_country")
    @classmethod
    def _v_country(cls, v: str) -> str:
        normalized = _normalize_country(v)
        if not _COUNTRY_RE.match(normalized):
            raise ValueError("destination_country must be 2-letter ISO code, e.g. 'US'")
        return normalized


class BindRequest(BaseModel):
    """Request body for POST /api/v2/insurance/bind."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(..., min_length=2, max_length=64)
    quote_id: str = Field(..., min_length=4, max_length=128, description="From POST /quote response")

    @field_validator("order_id")
    @classmethod
    def _v_order_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("order_id cannot be empty")
        return cleaned

    @field_validator("quote_id")
    @classmethod
    def _v_quote_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("quote_id cannot be empty")
        return cleaned


class ClaimRequest(BaseModel):
    """Request body for POST /api/v2/insurance/claim."""

    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(..., min_length=2, max_length=64)
    rejection_reason: str = Field(
        ...,
        min_length=2,
        max_length=512,
        description="Free text — consular 拒签信 reason / summary",
    )

    @field_validator("order_id")
    @classmethod
    def _v_order_id(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("order_id cannot be empty")
        return cleaned

    @field_validator("rejection_reason")
    @classmethod
    def _v_reason(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("rejection_reason must be at least 2 chars after trim")
        return cleaned


# --------------------------------------------------------------------------- #
# Responses                                                                   #
# --------------------------------------------------------------------------- #
class QuoteData(BaseModel):
    """Response body for POST /api/v2/insurance/quote."""

    model_config = ConfigDict(extra="forbid")

    quote_id: str
    policy_no: str = Field(..., description="Lookup key for POST /bind (same as quote_id in mock)")
    premium_cents: int = Field(..., ge=0)
    coverage_cents: int = Field(..., ge=0)
    currency: str = "CNY"
    created_at: str


class BindData(BaseModel):
    """Response body for POST /api/v2/insurance/bind."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str
    policy_no: str
    status: str = Field(..., description="Always 'bound' on success")
    bound_at: Optional[str] = None
    order_id: str
    premium_cents: int
    coverage_cents: int
    currency: str = "CNY"


class ClaimData(BaseModel):
    """Response body for POST /api/v2/insurance/claim."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    policy_id: str
    policy_no: str
    status: str = Field(..., description="Mock always returns 'approved'")
    payout_cents: int
    approved_at: Optional[str] = None
    order_id: str
    rejection_reason: str


class PolicyData(BaseModel):
    """Response body for GET /api/v2/insurance/{policy_id}.

    Mirrors `MockInsuranceProvider.get_policy` shape. Frontend can use
    this to render the same widget as POST /bind returns.
    """

    model_config = ConfigDict(extra="forbid")

    policy_id: str
    policy_no: str
    order_id: str
    status: str = Field(..., description="quoted | bound | claimed")
    applicant_age: int
    destination_country: str
    premium_cents: int
    coverage_cents: int
    currency: str = "CNY"
    created_at: str
    bound_at: Optional[str] = None
    claim_id: Optional[str] = None
    claim_status: Optional[str] = None
    payout_cents: Optional[int] = None
    claimed_at: Optional[str] = None
    rejection_reason: Optional[str] = None
