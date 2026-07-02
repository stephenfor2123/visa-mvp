"""Extend visa_countries with V2 frontend metadata.

Revision ID: 0011_countries_extend
Revises: 0010_admin_roles_users
Create Date: 2026-06-30 19:35:00.000000

Adds columns to ``visa_countries`` to support the V2 admin country-config
UI and the home-page country picker:

  - display_order      : int, default 0, indexed — frontend ordering
  - form_template_url  : text — public URL of the country-specific form template
  - description        : text — short blurb on the country card
  - flag_emoji         : varchar(16) — emoji glyph (e.g. 🇮🇩)
  - capital_city       : varchar(128) — capital city label

The ``enabled`` column already exists (added in 0007). We do NOT touch it here
— the V2 product spec reuses it as the V2 enable flag. ``visa_types`` already
exists too.

The migration is fully reversible — see ``downgrade`` for the inverse steps
(dropping the index first, then the columns).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0011_countries_extend"
down_revision = "0010_admin_roles_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- visa_countries: V2 frontend metadata ----
    op.add_column(
        "visa_countries",
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "visa_countries",
        sa.Column("form_template_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "visa_countries",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "visa_countries",
        sa.Column("flag_emoji", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "visa_countries",
        sa.Column("capital_city", sa.String(length=128), nullable=True),
    )
    # Index on display_order so /api/v2/admin/config/countries ORDER BY
    # display_order, country_code stays cheap as the table grows.
    op.create_index(
        "ix_visa_countries_display_order",
        "visa_countries",
        ["display_order"],
        unique=False,
    )

    # Backfill: assign per-row display_order = current alphabetical index so
    # the existing seeded countries keep a stable order after the migration.
    # Idempotent — if the table is empty this is a no-op.
    op.execute(
        sa.text(
            """
            UPDATE visa_countries
            SET display_order = (
                SELECT COUNT(*) FROM visa_countries AS vc2
                WHERE vc2.country_code <= visa_countries.country_code
            ) - 1
            """
        )
    )


def downgrade() -> None:
    # Inverse order of upgrade — drop the index first so dropping the
    # column does not leave dangling index references.
    op.drop_index("ix_visa_countries_display_order", table_name="visa_countries")
    op.drop_column("visa_countries", "capital_city")
    op.drop_column("visa_countries", "flag_emoji")
    op.drop_column("visa_countries", "description")
    op.drop_column("visa_countries", "form_template_url")
    op.drop_column("visa_countries", "display_order")