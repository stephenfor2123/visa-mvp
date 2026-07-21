"""Platform pricing schemas — public + admin (global + per destination)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class PlatformPricingResolved(BaseModel):
    """Resolved pricing for C-side display / checkout fallback."""

    list_price_usd: Decimal = Field(..., description="Regular / strikethrough price")
    promo_price_usd: Decimal = Field(..., description="Configured promo price")
    display_price_usd: Decimal = Field(..., description="Price shown to users right now")
    currency: str = "USD"
    is_promo: bool = Field(False, description="Whether promo window is active now")
    promo_enabled: bool = True
    promo_starts_at: Optional[datetime] = None
    promo_ends_at: Optional[datetime] = None
    display_price_cents: int = Field(..., ge=0)
    list_price_cents: int = Field(..., ge=0)
    # Resolution provenance (optional for C-side)
    country_code: Optional[str] = None
    visa_type: Optional[str] = None
    source: Optional[str] = Field(
        None,
        description="destination_exact | destination_country | global",
    )


class PlatformPricingAdminOut(BaseModel):
    """Full config row for admin editor (global singleton)."""

    id: int
    list_price_usd: Decimal
    promo_price_usd: Decimal
    currency: str
    promo_enabled: bool
    promo_starts_at: Optional[datetime] = None
    promo_ends_at: Optional[datetime] = None
    marketing_note: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    is_promo: bool = False
    display_price_usd: Decimal


class UpdatePlatformPricingRequest(BaseModel):
    list_price_usd: Decimal = Field(..., gt=0, description="Regular / strikethrough price")
    promo_price_usd: Decimal = Field(..., gt=0, description="Promotional price")
    currency: str = Field("USD", max_length=8)
    promo_enabled: bool = True
    promo_starts_at: Optional[datetime] = None
    promo_ends_at: Optional[datetime] = None
    marketing_note: Optional[str] = Field(None, max_length=2000)


class DestinationPricingOut(BaseModel):
    """One country + visa_type pricing row for admin list / editor."""

    id: Optional[int] = None
    country_code: str
    country_name: Optional[str] = None
    visa_type: str
    list_price_usd: Decimal
    promo_price_usd: Decimal
    currency: str = "USD"
    promo_enabled: bool = True
    promo_starts_at: Optional[datetime] = None
    promo_ends_at: Optional[datetime] = None
    marketing_note: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    is_promo: bool = False
    display_price_usd: Decimal
    inherited: bool = Field(
        False,
        description="True when falling back to global (no dedicated row yet)",
    )


class UpdateDestinationPricingRequest(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=8)
    visa_type: str = Field(..., min_length=1, max_length=32)
    list_price_usd: Decimal = Field(..., gt=0)
    promo_price_usd: Decimal = Field(..., gt=0)
    currency: str = Field("USD", max_length=8)
    promo_enabled: bool = True
    promo_starts_at: Optional[datetime] = None
    promo_ends_at: Optional[datetime] = None
    marketing_note: Optional[str] = Field(None, max_length=2000)


class DestinationPricingListOut(BaseModel):
    global_pricing: PlatformPricingAdminOut
    items: List[DestinationPricingOut]
