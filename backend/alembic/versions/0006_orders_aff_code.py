"""Add orders.aff_code — V2 §4.7 Affiliate integration (B-W9-3).

Revision ID: 0006_orders_aff_code
Revises: 0005_order_poll
Create Date: 2026-06-12 22:55:00.000000

Wires the OMS order service into the standalone Affiliate provider
delivered in B-W8-4. We store the partner `aff_code` on the order row
so that the `on_order_created` event hook can resolve it to a tracked
click_id at attribute-time (most partners get one click per aff_code
during the marketing window — multi-click resolution is a V2.1 concern).

Schema change (SQLite-friendly):
  - ADD COLUMN aff_code VARCHAR(32) NULL  on orders
  - CREATE INDEX ix_orders_aff_code      on orders(aff_code)

Why a single-column index (not composite with user_id):
  - Affiliate analytics rollups (clicks → orders → commission per partner)
    want fast lookups by aff_code alone. The OMS `list by user` query
    already has its own composite index (`idx_orders_user_created`).

Down-migration drops the index then the column. SQLite ≥ 3.35 supports
`DROP COLUMN`; we're on ≥ 3.40 via aiosqlite, so this is safe.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0006_orders_aff_code"
down_revision = "0005_order_poll"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("aff_code", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_orders_aff_code", "orders", ["aff_code"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_orders_aff_code", table_name="orders")
    op.drop_column("orders", "aff_code")