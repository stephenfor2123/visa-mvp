"""Add webhook_events table for Stripe callback deduplication (W16-3).

Revision ID: 0008_webhook_events
Revises: 0007_admin_tables
Create Date: 2026-06-14 23:30:00.000000

One new table:
  - webhook_events : deduplication log for processed webhook events.
    PK = Stripe event.id (e.g. "evt_3Nx...").  The DB unique constraint
    prevents double-processing of Stripe retry webhooks.

Indexes:
  - ix_webhook_events_provider_order_no : provider + order_no (payment lookups)
  - ix_webhook_events_processed_at       : TTL / monitoring queries

Reversible via DROP TABLE IF EXISTS.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0008_webhook_events"
down_revision = "0007_admin_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column(
            "event_id",
            sa.String(length=255),
            primary_key=True,
            comment="Stripe event.id — globally unique, the dedup key",
        ),
        sa.Column(
            "provider",
            sa.String(length=16),
            nullable=False,
            comment="'stripe' | 'mock'",
        ),
        sa.Column(
            "event_type",
            sa.String(length=64),
            nullable=False,
            comment="Raw gateway event type (e.g. 'payment_intent.succeeded')",
        ),
        sa.Column(
            "order_no",
            sa.String(length=32),
            nullable=True,
            comment="order_no resolved from event metadata",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="UTC timestamp of successful processing",
        ),
        sa.Column(
            "raw_payload",
            sa.Text(),
            nullable=True,
            comment="Full JSON payload — enables replay / audit",
        ),
    )
    op.create_index(
        "ix_webhook_events_provider_order_no",
        "webhook_events",
        ["provider", "order_no"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_events_processed_at",
        "webhook_events",
        ["processed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_events_processed_at", table_name="webhook_events")
    op.drop_index(
        "ix_webhook_events_provider_order_no", table_name="webhook_events"
    )
    op.drop_table("webhook_events")