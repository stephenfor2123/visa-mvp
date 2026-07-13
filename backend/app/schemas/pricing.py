"""Platform pricing schemas — public + admin."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

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


class PlatformPricingAdminOut(BaseModel):
    """Full config row for admin editor."""

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
    # resolved snapshot at read time
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
