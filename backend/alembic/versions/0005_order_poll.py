"""order_poll_log 表 — V2 §4.2.4 (state machine) + §4.3 RPA handoff

Revision ID: 0005_order_poll
Revises: 0004_orders
Create Date: 2026-06-11 21:30:00.000000

Creates one new table for the scheduler poll-tick audit log:

  order_poll_log
    - id            PK autoincrement
    - order_no      FK orders.order_no (ON DELETE CASCADE), indexed
    - polled_at     DateTime NOT NULL
    - status_before String(24) nullable (defensive)
    - status_after  String(24) NOT NULL
    - poll_source   String(24) NOT NULL  ('scheduler_tick'|'manual'|'rpa_callback')
    - notes         Text nullable

Indexes:
  - ix_order_poll_log_order_no         (single-column, on FK)
  - idx_order_poll_log_order_polled    (composite, primary query pattern)
  - idx_order_poll_log_source          (for "show last scheduler_tick" debugging)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0005_order_poll"
down_revision = "0004_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_poll_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("polled_at", sa.DateTime(), nullable=False),
        sa.Column("status_before", sa.String(length=24), nullable=True),
        sa.Column("status_after", sa.String(length=24), nullable=False),
        sa.Column("poll_source", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_no"],
            ["orders.order_no"],
            name="fk_order_poll_log_order_no",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_order_poll_log_order_no", "order_poll_log", ["order_no"], unique=False
    )
    op.create_index(
        "idx_order_poll_log_order_polled",
        "order_poll_log",
        ["order_no", "polled_at"],
        unique=False,
    )
    op.create_index(
        "idx_order_poll_log_source",
        "order_poll_log",
        ["poll_source"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_order_poll_log_source", table_name="order_poll_log")
    op.drop_index("idx_order_poll_log_order_polled", table_name="order_poll_log")
    op.drop_index("ix_order_poll_log_order_no", table_name="order_poll_log")
    op.drop_table("order_poll_log")