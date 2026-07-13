"""Singleton platform service-fee pricing (list + promo window)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PlatformPricing(Base):
    """Global Htex platform service fee — one row (id=1)."""

    __tablename__ = "platform_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    list_price_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Regular / strikethrough price (USD)"
    )
    promo_price_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Promotional price (USD)"
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    promo_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    promo_starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    promo_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    marketing_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
