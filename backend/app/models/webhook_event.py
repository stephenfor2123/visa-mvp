"""Webhook event deduplication table — Stripe callback reliability (W16-3).

Table: webhook_events

Purpose:
  - Stripe may retry a webhook up to 3 days with exponential back-off.
    Without deduplication, a retried `payment_intent.succeeded` would call
    `handle_notify` multiple times, risking duplicate affiliate payouts
    or duplicate status flips.
  - We store `event.id` (e.g. `evt_3Nx...`) as the primary key; the DB
    unique constraint is the dedup key.

Design:
  - PK = event_id (Stripe's idempotency key — globally unique per event).
  - provider = which gateway sent this event ('stripe', 'mock').
  - event_type = raw Stripe event type (e.g. 'payment_intent.succeeded').
  - order_no = resolved from metadata (nullable — some events have none).
  - raw_payload = full JSON so we can replay / audit without re-fetching.
  - processed_at = UTC timestamp for TTL / monitoring.

No FK to `orders` — we look up the order by `order_no` in metadata, and
the payment provider's `handle_notify` handles the "order not found" case.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WebhookEvent(Base):
    """Deduplication table for processed webhook events."""

    __tablename__ = "webhook_events"

    # Primary key — Stripe's `event.id` (e.g. "evt_3Nx...")
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Gateway that sent the event: 'stripe' | 'mock'
    provider: Mapped[str] = mapped_column(String(16), nullable=False)

    # Raw event type from the gateway
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # order_no resolved from event metadata (nullable for informational events)
    order_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # When we successfully processed (200 OK to the gateway)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Full JSON payload — enables replay / audit without re-fetching
    raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Index for looking up events by provider + order_no (payment queries)
    __table_args__ = (
        Index("ix_webhook_events_provider_order_no", "provider", "order_no"),
        Index("ix_webhook_events_processed_at", "processed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<WebhookEvent(event_id={self.event_id!r}, "
            f"provider={self.provider!r}, event_type={self.event_type!r})>"
        )