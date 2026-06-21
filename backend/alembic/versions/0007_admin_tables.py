"""Add admin tables — visa_countries + validation_rules (W14-3).

Revision ID: 0007_admin_tables
Revises: 0006_orders_aff_code
Create Date: 2026-06-14 09:15:00.000000

Two new tables:
  - visa_countries       : per-country visa portal config (enabled / base_url / RPA)
  - validation_rules     : AI validation rule definitions (DB-backed, upsertable)

No FK dependencies on new tables (they're standalone config tables).
Both tables are reversible via DROP TABLE IF EXISTS.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0007_admin_tables"
down_revision = "0006_orders_aff_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # visa_countries
    # -------------------------------------------------------------------------
    op.create_table(
        "visa_countries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("country_name_zh", sa.String(length=128), nullable=False),
        sa.Column("country_name_en", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("form_path", sa.Text(), nullable=True),
        sa.Column(
            "rpa_config", sa.Text(), nullable=True, comment="JSON object with RPA settings"
        ),
        sa.Column(
            "visa_types",
            sa.Text(),
            nullable=True,
            comment="JSON array of supported visa types",
        ),
        sa.Column("fee_usd", sa.JSON(), nullable=True),
        sa.Column("processing_days", sa.Integer(), nullable=True),
        sa.Column("extra", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visa_countries_country_code", "visa_countries", ["country_code"], unique=True)
    op.create_index("ix_visa_countries_enabled", "visa_countries", ["enabled"], unique=False)

    # Seed a few countries for development
    op.execute(
        """
        INSERT INTO visa_countries (country_code, country_name_zh, country_name_en, enabled, visa_types)
        VALUES
            ('ID', '印度尼西亚', 'Indonesia', TRUE, '["tourism","student"]'),
            ('VN', '越南', 'Vietnam', TRUE, '["tourism"]'),
            ('PH', '菲律宾', 'Philippines', FALSE, '["tourism"]')
        """
    )

    # -------------------------------------------------------------------------
    # validation_rules
    # -------------------------------------------------------------------------
    op.create_table(
        "validation_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("message_key", sa.String(length=128), nullable=False),
        sa.Column(
            "params", sa.Text(), nullable=True, comment="JSON object with rule-type params"
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_validation_rules_code", "validation_rules", ["code"], unique=True)
    op.create_index("ix_validation_rules_enabled", "validation_rules", ["enabled"], unique=False)

    # Seed a few sample rules
    op.execute(
        """
        INSERT INTO validation_rules (code, rule_type, severity, message_key, params, enabled)
        VALUES
            ('PASSPORT_EXPIRY_MIN_6M', 'expiry', 'error', 'passport_expiry_min_6m',
             '{"field": "expiry", "min_months": 6}', 1),
            ('PASSPORT_NO_FORMAT', 'regex', 'error', 'passport_no_format',
             '{"field": "passport_no", "pattern": "^[A-Z0-9]{6,12}$"}', 1),
            ('IMAGE_BLUR_THRESHOLD', 'image_quality', 'error', 'image_blur_threshold',
             '{"field": "__file__", "min_laplacian": 100}', 1)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_validation_rules_enabled", table_name="validation_rules")
    op.drop_index("ix_validation_rules_code", table_name="validation_rules")
    op.drop_table("validation_rules")

    op.drop_index("ix_visa_countries_enabled", table_name="visa_countries")
    op.drop_index("ix_visa_countries_country_code", table_name="visa_countries")
    op.drop_table("visa_countries")
