"""OrderPollLog — V2 §4.2.4 (state machine) + §4.3 RPA handoff.

Single append-only audit table that records every status-poll against an
order. Used by:

  * `POST /scheduler/poll-tick`           — internal scheduler loop
  * `POST /orders/{order_no}/poll-once`   — manual operator trigger
                                            (out of scope this Story)
  * RPA callback endpoints                — vendor pushes status update

The row answers three questions:
  1. What was the order's status before the poll?
  2. What did the poll decide?
  3. Did anything change? (status_after != status_before)

`status_after == status_before` rows still get written so we have a record
of "polled but no change" — useful for debugging "why didn't my RPA fire"
support tickets. The caller can filter by `status_before != status_after`
to see only true transitions.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


# --------------------------------------------------------------------------- #
# Enums (kept as plain string constants for SQLite friendliness)             #
# --------------------------------------------------------------------------- #
# Mirrors app.models.order.ORDER_STATUSES but only the values that the
# poll service can produce. `closed` is included for completeness (RPA
# sometimes emits a final closed state) but is not a transition the
# scheduler tick itself emits.
POLL_STATUSES: tuple[str, ...] = (
    "submitted",
    "reviewing",
    "approved",
    "rejected",
    "closed",
    "abnormal",
    "failed",
)

# Who initiated the poll
POLL_SOURCES: tuple[str, ...] = (
    "scheduler_tick",   # POST /scheduler/poll-tick from internal cron
    "manual",           # admin / operator button on the dashboard
    "rpa_callback",     # RPA vendor pushed us a webhook
)


# --------------------------------------------------------------------------- #
# OrderPollLog                                                                 #
# --------------------------------------------------------------------------- #
class OrderPollLog(Base):
    __tablename__ = "order_poll_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business order_no (denormalized so we don't have to JOIN orders for the
    # common "show me the poll history of order X" lookup). Indexed because
    # it's the primary query predicate.
    order_no: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orders.order_no", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    polled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=None
    )

    # Status before / after. Nullable only for the very first synthetic
    # "no prior state" row that shouldn't happen in practice — kept
    # optional defensively so a corrupted upstream can't blow up inserts.
    status_before: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    status_after: Mapped[str] = mapped_column(String(24), nullable=False)

    # scheduler_tick / manual / rpa_callback
    poll_source: Mapped[str] = mapped_column(String(24), nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_order_poll_log_order_polled", "order_no", "polled_at"),
        Index("idx_order_poll_log_source", "poll_source"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<OrderPollLog id={self.id} order_no={self.order_no} "
            f"{self.status_before}→{self.status_after} src={self.poll_source}>"
        )