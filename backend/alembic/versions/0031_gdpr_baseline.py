"""GDPR baseline: consents, retention, age gate, processing restriction.

Revision ID: 0031_gdpr_baseline
Revises: 0030_destination_pricing
Create Date: 2026-07-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_gdpr_baseline"
down_revision = "0030_destination_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "age_confirmed_16_at",
            sa.DateTime(),
            nullable=True,
            comment="When user confirmed they are 16+ (Art.8)",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "processing_restricted",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Art.18 restriction / Art.21 objection flag",
        ),
    )

    op.add_column(
        "applicants",
        sa.Column(
            "is_minor",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Applicant under 16 — guardian account required",
        ),
    )
    op.add_column(
        "applicants",
        sa.Column(
            "guardian_relationship",
            sa.String(length=64),
            nullable=True,
            comment="Relationship of account holder to minor applicant",
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "retention_anchor_at",
            sa.DateTime(),
            nullable=True,
            comment="Terminal-state timestamp for 90d/180d retention purge",
        ),
    )
    op.create_index("ix_orders_retention_anchor_at", "orders", ["retention_anchor_at"])

    op.create_table(
        "user_consents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.UniqueConstraint("user_id", "purpose", "version", name="uq_user_consent_purpose_ver"),
    )


def downgrade() -> None:
    op.drop_table("user_consents")
    op.drop_index("ix_orders_retention_anchor_at", table_name="orders")
    op.drop_column("orders", "retention_anchor_at")
    op.drop_column("applicants", "guardian_relationship")
    op.drop_column("applicants", "is_minor")
    op.drop_column("users", "processing_restricted")
    op.drop_column("users", "age_confirmed_16_at")
