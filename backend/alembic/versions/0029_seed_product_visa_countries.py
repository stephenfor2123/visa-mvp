"""Seed product visa_countries so admin toggles match homepage visas.

Revision ID: 0029_seed_product_visa_countries
Revises: 0028_analytics_events

Production historically only had legacy ID/VN/PH in visa_countries (0007),
while the public picker serves US/GB/AU/DE/FR. We do not file Indonesia /
Vietnam / Philippines visas — those rows are deleted here. Product
destination rows are upserted instead.
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0029_seed_product_visa_countries"
down_revision = "0028_analytics_events"
branch_labels = None
depends_on = None

# (code, zh, en, emoji, display_order, visa_types)
_PRODUCT = (
    ("US", "美国", "United States", "🇺🇸", 1, ["tourism", "student"]),
    ("AU", "澳大利亚", "Australia", "🇦🇺", 2, ["tourism"]),
    ("GB", "英国", "United Kingdom", "🇬🇧", 3, ["tourism"]),
    ("DE", "德国(申根)", "Germany (Schengen)", "🇩🇪", 4, ["tourism"]),
    ("FR", "法国(申根)", "France (Schengen)", "🇫🇷", 5, ["tourism"]),
)

# Not fileable destinations — remove from admin country config entirely.
# ID/VN remain customer *markets* (passport holders) elsewhere; they must
# not appear as visa_countries rows.
_REMOVE_FROM_VISA_COUNTRIES = (
    "ID", "VN", "PH", "JP", "CA", "SG", "NZ", "KR", "TH", "MY",
)


def upgrade() -> None:
    bind = op.get_bind()

    for code in _REMOVE_FROM_VISA_COUNTRIES:
        bind.execute(
            sa.text("DELETE FROM visa_countries WHERE country_code = :code"),
            {"code": code},
        )

    for code, zh, en, emoji, order, types in _PRODUCT:
        types_json = json.dumps(types, ensure_ascii=False)
        existing = bind.execute(
            sa.text("SELECT id FROM visa_countries WHERE country_code = :code"),
            {"code": code},
        ).fetchone()
        if existing is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO visa_countries (
                        country_code, country_name_zh, country_name_en,
                        enabled, display_order, visa_types, flag_emoji
                    ) VALUES (
                        :code, :zh, :en, 1, :ord, :types, :emoji
                    )
                    """
                ),
                {
                    "code": code,
                    "zh": zh,
                    "en": en,
                    "ord": order,
                    "types": types_json,
                    "emoji": emoji,
                },
            )
        else:
            # Fill display metadata; do not overwrite an operator's enabled flag
            bind.execute(
                sa.text(
                    """
                    UPDATE visa_countries
                    SET country_name_zh = :zh,
                        country_name_en = :en,
                        display_order = :ord,
                        visa_types = :types,
                        flag_emoji = COALESCE(NULLIF(flag_emoji, ''), :emoji)
                    WHERE country_code = :code
                    """
                ),
                {
                    "code": code,
                    "zh": zh,
                    "en": en,
                    "ord": order,
                    "types": types_json,
                    "emoji": emoji,
                },
            )

        # Mirror enabled onto destinations (UK↔GB)
        codes = [code]
        if code == "GB":
            codes.append("UK")
        for dest_code in codes:
            bind.execute(
                sa.text(
                    """
                    UPDATE visa_destinations
                    SET enabled = (
                        SELECT enabled FROM visa_countries
                        WHERE country_code = :vc_code
                    )
                    WHERE country_code = :dest_code
                    """
                ),
                {"vc_code": code, "dest_code": dest_code},
            )


def downgrade() -> None:
    # Additive product seeds / destructive legacy deletes are not reversed.
    pass
