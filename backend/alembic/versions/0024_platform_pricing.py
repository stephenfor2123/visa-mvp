"""Platform pricing singleton — list price + promo window

Revision ID: 0024_platform_pricing
Revises: 0023_order_state_v2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_platform_pricing"
down_revision = "0023_order_state_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_pricing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("list_price_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("promo_price_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("promo_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("promo_starts_at", sa.DateTime(), nullable=True),
        sa.Column("promo_ends_at", sa.DateTime(), nullable=True),
        sa.Column("marketing_note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "INSERT INTO platform_pricing "
            "(id, list_price_usd, promo_price_usd, currency, promo_enabled, "
            "promo_starts_at, promo_ends_at, marketing_note) "
            "VALUES "
            "(1, 99.90, 19.90, 'USD', 1, "
            "'2026-07-15 00:00:00', '2026-08-15 23:59:59', "
            "'Launch promo Jul 15 – Aug 15, 2026')"
        )
    )


def downgrade() -> None:
    op.drop_table("platform_pricing")
