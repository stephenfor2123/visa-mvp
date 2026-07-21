"""Per-destination (country + visa_type) platform service-fee pricing."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Country-wide default when no exact visa_type row exists
VISA_TYPE_ALL = "*"


class DestinationPricing(Base):
    """Htex platform fee for one country (+ optional visa_type).

    Lookup order in PricingService:
      1) exact (country_code, visa_type)
      2) country default (country_code, '*')
      3) global platform_pricing (id=1)
    """

    __tablename__ = "destination_pricing"
    __table_args__ = (
        UniqueConstraint(
            "country_code",
            "visa_type",
            name="uq_destination_pricing_country_visa",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    visa_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=VISA_TYPE_ALL,
        comment="tourism|student|… or * for all types of this country",
    )
    list_price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    promo_price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    promo_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    promo_starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    promo_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    marketing_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
