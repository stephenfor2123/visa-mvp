"""AnalyticsEvent — product funnel / 埋点 events (client + server)."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, default=_new_uuid)

    event_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    country_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True, index=True)
    order_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)

    props: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="client")
    path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_analytics_events_name_created", "event_name", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnalyticsEvent {self.event_name} user={self.user_id}>"
