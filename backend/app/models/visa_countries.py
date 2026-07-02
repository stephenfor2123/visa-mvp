"""VisaCountries — country configuration for the visa application portal.

Stores per-country settings: enabled flag, display order, base URL, form path,
visa types, RPA config, i18n display names, and frontend metadata (emoji,
capital, description, form template URL).
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

    # Status (V2 enabled flag)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Frontend display order (smaller = earlier; defaults to 0)
    display_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, index=True,
        comment="Frontend display order (ascending)"
    )

    # RPA / portal routing
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_template_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Public URL of the country-specific form template"
    )
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

    # Frontend display metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Short description shown on the country card"
    )
    flag_emoji: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, comment="Flag emoji (e.g. 🇮🇩)"
    )
    capital_city: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="Capital city shown on the country card"
    )

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
