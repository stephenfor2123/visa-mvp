"""User ORM model — V2 §4.1 / §4.1.4.

Per V2 §4.1.5: phone + phone_country are the natural identifiers.
We keep an autoincrement `id` as the stable primary key (FK target),
and a public `uuid` for external APIs.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:  # avoid circular imports at runtime
    from app.models.user_session import UserSession


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_new_uuid)

    # Identity
    phone: Mapped[str] = mapped_column(String(32), index=True)
    phone_country: Mapped[str] = mapped_column(String(8), default="+86")

    # Credentials
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Profile
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    language_pref: Mapped[str] = mapped_column(String(8), default="zh-CN")

    # Status — V2 lifecycle: active / pending_destroy / destroyed / disabled
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)

    # MFA — V2 §4.1 MFA
    mfa_enabled: Mapped[bool] = mapped_column(default=False, index=True)
    mfa_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # "totp" | "sms"
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # encrypted TOTP secret
    mfa_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # backup SMS phone
    mfa_phone_country: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    # Misc
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<User id={self.id} phone={self.phone_country}{self.phone}>"
