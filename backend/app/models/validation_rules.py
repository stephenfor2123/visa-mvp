"""ValidationRules — AI validation rule definitions stored in DB.

The rules JSON is the same shape as the bundled validation_rules.json used by
ValidationEngine; storing them in the DB lets admins edit rules without redeploying.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ValidationRule(Base):
    """AI validation rule — mirrors the JSON rule shape from V2 §5.2."""

    __tablename__ = "validation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Rule identity (matches the JSON 'code' field)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # Rule metadata
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # error / warning
    message_key: Mapped[str] = mapped_column(String(128), nullable=False)

    # Rule body — full JSON params stored as Text
    params: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON object with rule-type-specific params"
    )

    # Active flag
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ValidationRule {self.code} enabled={self.enabled}>"
