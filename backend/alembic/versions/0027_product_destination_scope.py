"""Align destination enabled flags with product scope.

Revision ID: 0027_product_destination_scope
Revises: 0026_merge_oauth_ds160

Product destinations (enabled): US / GB / UK / AU / DE / FR
Non-product (disabled): ID / VN / JP / CA / SG / NZ / KR / TH / PH / MY / …

Also disable legacy visa_countries seed rows for ID / VN (those were
mistakenly treated as fileable visa destinations; they are customer markets).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_product_destination_scope"
down_revision = "0026_merge_oauth_ds160"
branch_labels = None
depends_on = None

_PRODUCT = ("US", "GB", "UK", "AU", "DE", "FR")
_NON_PRODUCT = ("ID", "VN", "JP", "CA", "SG", "NZ", "KR", "TH", "PH", "MY")


def upgrade() -> None:
    bind = op.get_bind()

    # visa_destinations — public destination picker source
    for code in _PRODUCT:
        bind.execute(
            sa.text(
                "UPDATE visa_destinations SET enabled = 1 WHERE country_code = :code"
            ),
            {"code": code},
        )
    for code in _NON_PRODUCT:
        bind.execute(
            sa.text(
                "UPDATE visa_destinations SET enabled = 0 WHERE country_code = :code"
            ),
            {"code": code},
        )

    # visa_countries — admin / RPA config table (0007 seeded ID/VN as enabled)
    for code in _NON_PRODUCT:
        bind.execute(
            sa.text(
                "UPDATE visa_countries SET enabled = 0 WHERE country_code = :code"
            ),
            {"code": code},
        )
    for code in _PRODUCT:
        bind.execute(
            sa.text(
                "UPDATE visa_countries SET enabled = 1 WHERE country_code = :code"
            ),
            {"code": code},
        )


def downgrade() -> None:
    # Best-effort restore of pre-scope seed: only US enabled on destinations;
    # ID/VN enabled on visa_countries (as in 0007). Not a perfect inverse.
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE visa_destinations SET enabled = 0"))
    bind.execute(
        sa.text("UPDATE visa_destinations SET enabled = 1 WHERE country_code = 'US'")
    )
    bind.execute(
        sa.text(
            "UPDATE visa_countries SET enabled = 1 "
            "WHERE country_code IN ('ID', 'VN')"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE visa_countries SET enabled = 0 "
            "WHERE country_code IN ('PH')"
        )
    )
