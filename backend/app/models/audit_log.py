"""AuditLog — append-only event log for sensitive actions (V2 §4.1.4)."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, default=_new_uuid)

    # Who acted
    actor_type: Mapped[str] = mapped_column(String(16))   # user / admin / system
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # What happened
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. user.login

    # On what
    target_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Free-form structured context (request id, IP, user-agent, etc.)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_log_actor_action", "actor_type", "actor_id", "action"),
        # W16 performance: the admin /logs endpoint ALWAYS sorts by
        # created_at DESC and frequently filters by action / actor_type.
        # A composite (created_at, action, actor_type) index lets the
        # planner do an index range scan + use a sort-elimination in one
        # pass, instead of a full scan + sort.
        Index(
            "ix_audit_log_created_action_actor",
            "created_at",
            "action",
            "actor_type",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.actor_type}:{self.actor_id} {self.action}>"
