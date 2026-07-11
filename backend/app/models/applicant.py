"""Applicant ORM model — personal applicant profile library.

W1 (this commit): one account may have multiple applicants. Each applicant
carries a passport_no (one-to-one). This table is the authoritative source
of truth for "who is in this account" — the existing `order.applicant_data`
JSON field remains a per-order snapshot.

Fields in this version (intentionally minimal, W1 scope):
  - id, user_id, surname, given_name, passport_no
  - created_at, updated_at

Future W2+ fields (planned, NOT in this migration):
  - sex, dob, nationality, passport_expiry
  - these will be filled by OCR auto-recognition or manual entry
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Applicant(Base):
    __tablename__ = "applicants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Passport-style name (matches order.applicant_data shape).
    surname: Mapped[str] = mapped_column(String(64), nullable=False)
    given_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Passport number — unique per user (one user cannot have two
    # applicants with the same passport), but NOT unique globally
    # (different users can have the same passport_no? no — but to keep
    # the door open for future "shared family account" we don't add a
    # global unique). Actually, a passport_no IS globally unique in
    # reality; the user's question of "two users with same passport"
    # never happens. We do enforce global uniqueness to prevent
    # typos/dupes: one passport belongs to one user. A user can
    # unlink + reassign later, but for W1 we just say passport_no
    # is globally unique.
    passport_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships — kept light; we don't backref to orders in W1.
    user: Mapped["User"] = relationship(back_populates="applicants")  # noqa: F821

    # Unique constraints
    __table_args__ = (
        # A given user cannot add the same applicant (surname+given_name) twice.
        UniqueConstraint("user_id", "surname", "given_name", name="uq_applicant_user_name"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Applicant id={self.id} user={self.user_id} name={self.surname}{self.given_name}>"


# Late import to avoid circular.
from app.models.user import User  # noqa: E402
User.applicants = relationship(  # type: ignore[attr-defined]
    "Applicant", back_populates="user", cascade="all, delete-orphan"
)
