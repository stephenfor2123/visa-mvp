"""UserSession — refresh-token + device fingerprint bookkeeping."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.user import User


def _new_uuid() -> str:
    return str(uuid.uuid4())


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_new_uuid)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Refresh-token (hashed) — we never store raw tokens.
    refresh_token_hash: Mapped[str] = mapped_column(String(255), index=True)

    # Device / connection metadata
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Validity
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="sessions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserSession id={self.id} user_id={self.user_id}>"
