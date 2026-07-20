"""Add ds160_code_hash; stop relying on plaintext plugin codes in DB

Revision ID: 0021_ds160_code_hash
Revises: 0020_password_changed_at
Create Date: 2026-07-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0021_ds160_code_hash"
down_revision = "0020_password_changed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "ds160_code_hash",
            sa.String(length=64),
            nullable=True,
            comment="SHA-256 hex of DS-160 redeem code; plaintext never stored",
        ),
    )
    op.create_index("ix_orders_ds160_code_hash", "orders", ["ds160_code_hash"])


def downgrade() -> None:
    op.drop_index("ix_orders_ds160_code_hash", table_name="orders")
    op.drop_column("orders", "ds160_code_hash")
