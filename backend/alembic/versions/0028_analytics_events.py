"""Add analytics_events table for product 埋点.

Revision ID: 0028_analytics_events
Revises: 0027_product_destination_scope
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_analytics_events"
down_revision = "0027_product_destination_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("order_no", sa.String(length=32), nullable=True),
        sa.Column("props", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default="client",
        ),
        sa.Column("path", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_index("ix_analytics_events_event_name", "analytics_events", ["event_name"])
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"])
    op.create_index("ix_analytics_events_session_id", "analytics_events", ["session_id"])
    op.create_index("ix_analytics_events_country_code", "analytics_events", ["country_code"])
    op.create_index("ix_analytics_events_order_no", "analytics_events", ["order_no"])
    op.create_index("ix_analytics_events_created_at", "analytics_events", ["created_at"])
    op.create_index(
        "ix_analytics_events_name_created",
        "analytics_events",
        ["event_name", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_events_name_created", table_name="analytics_events")
    op.drop_index("ix_analytics_events_created_at", table_name="analytics_events")
    op.drop_index("ix_analytics_events_order_no", table_name="analytics_events")
    op.drop_index("ix_analytics_events_country_code", table_name="analytics_events")
    op.drop_index("ix_analytics_events_session_id", table_name="analytics_events")
    op.drop_index("ix_analytics_events_user_id", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_name", table_name="analytics_events")
    op.drop_table("analytics_events")
