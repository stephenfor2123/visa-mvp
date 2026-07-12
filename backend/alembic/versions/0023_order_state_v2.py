"""Order state v2: paid/completed/cancelled + refund + portal milestone fields

Revision ID: 0023_order_state_v2
Revises: 0022_email_codes
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_order_state_v2"
down_revision = "0022_email_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("locked_until", sa.DateTime(), nullable=True, comment="Payment deadline (1h after create)"),
    )
    op.add_column(
        "orders",
        sa.Column("paid_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("diagnosis_completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="AI diagnosis done — Htex service complete"),
    )
    op.add_column(
        "orders",
        sa.Column("portal_submitted_at", sa.DateTime(), nullable=True, comment="User confirmed embassy portal submission"),
    )
    op.add_column(
        "orders",
        sa.Column("portal_submitted_source", sa.String(16), nullable=True, comment="extension | user | admin"),
    )
    op.add_column(
        "orders",
        sa.Column("refund_status", sa.String(16), nullable=False, server_default="none"),
    )
    op.add_column("orders", sa.Column("refund_reason", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("refund_amount", sa.Numeric(10, 2), nullable=True))
    op.add_column("orders", sa.Column("refund_requested_at", sa.DateTime(), nullable=True))
    op.add_column("orders", sa.Column("refund_approved_at", sa.DateTime(), nullable=True))
    op.add_column("orders", sa.Column("refund_reviewed_by", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("refunded_at", sa.DateTime(), nullable=True))

    # Backfill portal_submitted_at from DS-160 column
    op.execute(
        "UPDATE orders SET portal_submitted_at = ds160_portal_submitted_at "
        "WHERE ds160_portal_submitted_at IS NOT NULL AND portal_submitted_at IS NULL"
    )


def downgrade() -> None:
    for col in (
        "refunded_at",
        "refund_reviewed_by",
        "refund_approved_at",
        "refund_requested_at",
        "refund_amount",
        "refund_reason",
        "refund_status",
        "portal_submitted_source",
        "portal_submitted_at",
        "completed_at",
        "diagnosis_completed_at",
        "paid_at",
        "locked_until",
    ):
        op.drop_column("orders", col)
