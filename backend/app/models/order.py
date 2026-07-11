"""Order ORM models — V2 §4.2 (Order Service).

Three tables:
  - orders                : main order row (one per user-submitted visa application)
  - order_status_history  : append-only log of state transitions (V2 §4.2.4 state machine)
  - order_messages        : per-order notification messages (in-app / push / email / sms)

We map the V2 Postgres schema to SQLite-friendly types:
  - JSONB        -> Text (JSON 字符串)
  - BIGINT[]     -> Text (JSON 字符串数组)
  - NUMERIC(10,2)-> Numeric (DECIMAL)
  - TIMESTAMPTZ  -> DateTime
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Order status machine (V2 §4.2.4)                                            #
# --------------------------------------------------------------------------- #
# Lifecycle:
#   created → submitted → reviewing → approved | rejected → closed
#   abnormal / failed are terminal-exception states (set by system / scheduler)
# Cancel is a user-only transition (created → closed) per W3-3 enforcement.
# Admin overrides may move the order to any state in VALID_TRANSITIONS, but
# the same validator is shared between user endpoints (cancel/submit) and
# the admin override (`admin_service.update_order_status`) so the audit
# trail and the OrderStatusHistory rows stay consistent.
ORDER_STATUSES: tuple[str, ...] = (
    "created",
    "submitted",
    "reviewing",
    "approved",
    "rejected",
    "closed",
    "abnormal",
    "failed",
)

VISA_TYPES: tuple[str, ...] = ("tourism", "student")

# Statuses that can still be acted on by the user (cancel, submit)
CANCELLABLE_STATUSES: frozenset[str] = frozenset({"created"})

# Active statuses used in idx_orders_status (V2 §4.2.2 partial index intent)
ACTIVE_STATUSES: tuple[str, ...] = ("created", "submitted", "reviewing")

# Terminal states — no outbound transitions allowed.
TERMINAL_STATUSES: frozenset[str] = frozenset({"closed", "abnormal", "failed"})

# --------------------------------------------------------------------------- #
# VALID_TRANSITIONS (W34 — single source of truth)                            #
# --------------------------------------------------------------------------- #
# The map is read by `is_valid_transition()` everywhere a status flip is
# attempted (user cancel / submit, admin override, scheduler poll). Adding a
# new state means editing this dict + the ORDER_STATUSES tuple — both
# kept in one place so the state machine stays coherent.
#
# Diagram:
#   created   → submitted, closed
#   submitted → reviewing, closed, abnormal, failed
#   reviewing → approved, rejected, closed, abnormal, failed
#   approved  → closed
#   rejected  → closed
#   closed    → (terminal)
#   abnormal  → (terminal, system-only)
#   failed    → (terminal, system-only)
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "created":   frozenset({"submitted", "closed"}),
    "submitted": frozenset({"reviewing", "closed", "abnormal", "failed"}),
    "reviewing": frozenset({"approved", "rejected", "closed", "abnormal", "failed"}),
    "approved":  frozenset({"closed"}),
    "rejected":  frozenset({"closed"}),
    "closed":    frozenset(),
    "abnormal":  frozenset(),
    "failed":    frozenset(),
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """True if `from_status → to_status` is allowed by the state machine.

    Same-state "transitions" (e.g. reviewing → reviewing) are rejected —
    we want callers to use an explicit "no-op" path if they really mean it,
    so audit logs only ever represent actual changes.
    """
    if from_status not in VALID_TRANSITIONS:
        return False
    if to_status not in ORDER_STATUSES:
        return False
    return to_status in VALID_TRANSITIONS[from_status]


def next_statuses(from_status: str) -> frozenset[str]:
    """Return the set of statuses reachable from `from_status`.

    Convenience for the admin UI to render only the buttons that will
    actually be accepted by the server. Returns an empty frozenset for
    terminal states.
    """
    return VALID_TRANSITIONS.get(from_status, frozenset())


# Source values for order_status_history.source
STATUS_SOURCES: tuple[str, ...] = ("user", "scheduler", "rpa", "system", "admin")

# Message channels for order_messages
MESSAGE_CHANNELS: tuple[str, ...] = ("inapp", "push", "email", "sms")


# --------------------------------------------------------------------------- #
# Order                                                                       #
# --------------------------------------------------------------------------- #
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_new_uuid)

    # Business order number — V2-20260611-000123 format (V2 §4.2.2)
    order_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)

    # Ownership
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Routing
    destination_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    visa_type: Mapped[str] = mapped_column(String(16), nullable=False)

    # State machine
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="created", index=True
    )

    # Pricing
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="0"
    )
    currency: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="USD"
    )

    # RPA / external integration
    rpa_task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    destination_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Affiliate / referral code (V2 §4.7). Nullable — most orders come
    # in direct (no partner link). When present, the B-W9-3 OMS event hook
    # auto-binds the order to the partner via the affiliate provider's
    # `attribute(order_id, click_id)` API. We store `aff_code` here and
    # resolve the click_id at attribution time from the partner's tracked
    # clicks; V2.1 will move the click_id into a separate column once we
    # have multi-click-per-aff_code flows.
    aff_code: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, index=True
    )

    # Applicant form data + material association
    # applicant_data: stored as JSON text; material_ids: stored as JSON array
    applicant_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    material_ids: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of material.id, e.g. [12, 34, 56]",
    )

    # Timestamps
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Free-form bag
    extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # === DS-160 browser extension (W48 v0.2) ============================ #
    # 12-digit base30 code binding the order's applicant_data snapshot to a
    # fingerprint.  When any DS-160-relevant field changes, the fingerprint
    # changes and the old code is rejected on redeem with 409 ARCHIVE_CHANGED.
    # See backend/app/core/ds160.py + browser-extension/DESIGN-v0.2.md.
    ds160_code: Mapped[Optional[str]] = mapped_column(
        String(12), nullable=True, index=True,
        comment="12-char base30 code; null until user requests it via /api/v2/ds160/code",
    )
    ds160_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="SHA-256 hex (32 chars) of normalized applicant_data snapshot",
    )
    ds160_code_issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ds160_code_consumed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
        comment="Total successful redeems (audit + soft-rate-limit)",
    )
    ds160_last_redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ds160_code_revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0",
        comment="User-initiated rotate: old codes rejected even if fingerprint matches",
    )
    # JSON list of 12-char codes that have been explicitly revoked by force_rotate.
    # P1 swap: when an order has more than a handful of revocations, replace this
    # with a dedicated revoked_codes table keyed by (order_id, code).
    ds160_revoked_codes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment='JSON list of revoked 12-char codes, e.g. ["K7H3N9XRA2BQ", ...]',
    )
    # ==================================================================== #

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.created_at",
    )
    messages: Mapped[list["OrderMessage"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderMessage.created_at",
    )

    __table_args__ = (
        Index("idx_orders_user_created", "user_id", "created_at"),
        # V2 §4.2.2 mentions partial indexes on status & rpa_task_id.
        # SQLite supports partial indexes; we replicate intent via composite indexes.
        Index("idx_orders_status_active", "status"),
        Index("idx_orders_rpa", "rpa_task_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<Order id={self.id} order_no={self.order_no} status={self.status}>"


# --------------------------------------------------------------------------- #
# Order status history                                                        #
# --------------------------------------------------------------------------- #
class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    from_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)

    # user / scheduler / rpa / system
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship(back_populates="status_history")

    __table_args__ = (
        Index("idx_status_history_order", "order_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (
            f"<OrderStatusHistory order_id={self.order_id} "
            f"{self.from_status}→{self.to_status} src={self.source}>"
        )


# --------------------------------------------------------------------------- #
# Order message                                                               #
# --------------------------------------------------------------------------- #
class OrderMessage(Base):
    __tablename__ = "order_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # inapp / push / email / sms
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship(back_populates="messages")

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<OrderMessage id={self.id} order_id={self.order_id} channel={self.channel}>"
