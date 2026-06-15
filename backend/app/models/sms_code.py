"""SmsCode — short-lived OTP records (V2 §4.1.4).

We store `code_hash` (bcrypt) — never the raw code. Used by register,
login, reset, destroy flows.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SmsCode(Base):
    __tablename__ = "sms_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Target
    phone: Mapped[str] = mapped_column(String(32), index=True)
    phone_country: Mapped[str] = mapped_column(String(8), default="+86")

    # Auth — we hash the OTP before persisting
    code_hash: Mapped[str] = mapped_column(String(255))

    # Why the code was sent
    purpose: Mapped[str] = mapped_column(String(16), index=True)  # register/login/reset/destroy

    # Lifecycle
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    send_count: Mapped[int] = mapped_column(Integer, default=1)  # for "resend" cooldown
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_sms_codes_phone_purpose", "phone", "phone_country", "purpose"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SmsCode id={self.id} phone={self.phone_country}{self.phone} purpose={self.purpose}>"
