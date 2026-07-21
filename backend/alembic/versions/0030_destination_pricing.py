"""Per-country / visa_type destination pricing.

Revision ID: 0030_destination_pricing
Revises: 0029_seed_product_visa_countries
"""
from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0030_destination_pricing"
down_revision = "0029_seed_product_visa_countries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "destination_pricing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(8), nullable=False),
        sa.Column("visa_type", sa.String(32), nullable=False, server_default="*"),
        sa.Column("list_price_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("promo_price_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("promo_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("promo_starts_at", sa.DateTime(), nullable=True),
        sa.Column("promo_ends_at", sa.DateTime(), nullable=True),
        sa.Column("marketing_note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "country_code",
            "visa_type",
            name="uq_destination_pricing_country_visa",
        ),
    )
    op.create_index(
        "ix_destination_pricing_country_code",
        "destination_pricing",
        ["country_code"],
    )

    # Seed one row per (destination, visa_type) from global platform_pricing + destinations
    bind = op.get_bind()
    global_row = bind.execute(
        sa.text(
            "SELECT list_price_usd, promo_price_usd, currency, promo_enabled, "
            "promo_starts_at, promo_ends_at, marketing_note "
            "FROM platform_pricing WHERE id = 1"
        )
    ).fetchone()
    if global_row is None:
        list_p, promo_p = 99.90, 19.90
        currency, promo_enabled = "USD", True
        starts = datetime(2026, 7, 15, 0, 0, 0)
        ends = datetime(2026, 8, 15, 23, 59, 59)
        note = "Seeded from defaults"
    else:
        list_p = float(global_row[0])
        promo_p = float(global_row[1])
        currency = global_row[2] or "USD"
        promo_enabled = bool(global_row[3])
        starts = global_row[4]
        ends = global_row[5]
        note = global_row[6] or "Copied from global platform pricing"

    dests = bind.execute(
        sa.text(
            "SELECT country_code, visa_types FROM visa_destinations WHERE enabled = 1"
        )
    ).fetchall()
    now = datetime.utcnow()
    for country_code, visa_types_raw in dests:
        try:
            types = json.loads(visa_types_raw or "[]")
        except Exception:
            types = []
        if not isinstance(types, list) or not types:
            types = ["tourism"]
        for vt in types:
            vt_norm = str(vt or "tourism").strip().lower() or "tourism"
            bind.execute(
                sa.text(
                    "INSERT INTO destination_pricing "
                    "(country_code, visa_type, list_price_usd, promo_price_usd, currency, "
                    "promo_enabled, promo_starts_at, promo_ends_at, marketing_note, updated_at) "
                    "VALUES (:cc, :vt, :lp, :pp, :cur, :pe, :ps, :pe2, :note, :ua)"
                ),
                {
                    "cc": str(country_code).upper(),
                    "vt": vt_norm,
                    "lp": list_p,
                    "pp": promo_p,
                    "cur": currency,
                    "pe": promo_enabled,
                    "ps": starts,
                    "pe2": ends,
                    "note": note,
                    "ua": now,
                },
            )


def downgrade() -> None:
    op.drop_index("ix_destination_pricing_country_code", table_name="destination_pricing")
    op.drop_table("destination_pricing")
