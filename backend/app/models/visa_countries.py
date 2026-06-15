"""VisaCountries — country configuration for the visa application portal.

Stores per-country settings: enabled flag, base URL, form path, visa types,
RPA config, and i18n display names.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class VisaCountry(Base):
    """Country configuration table — one row per supported visa country."""

    __tablename__ = "visa_countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Country identifiers
    country_code: Mapped[str] = mapped_column(
        String(8), unique=True, index=True, nullable=False
    )
    country_name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    country_name_en: Mapped[str] = mapped_column(String(128), nullable=False)

    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # RPA / portal routing
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rpa_config: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON object with RPA per-country settings"
    )

    # Visa types supported (JSON array, e.g. ["tourism", "student"])
    visa_types: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON array of supported visa types"
    )

    # Fee / duration info
    fee_usd: Mapped[Optional[float]] = mapped_column(
        JSON, nullable=True, comment="fee_usd (float) or null"
    )
    processing_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Free-form extra metadata
    extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VisaCountry {self.country_code} enabled={self.enabled}>"
