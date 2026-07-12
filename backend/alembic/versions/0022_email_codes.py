"""Add email_codes table for registration verification OTPs.

Revision ID: 0022_email_codes
Revises: 0021_ds160_portal_submitted
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_email_codes"
down_revision = "0021_ds160_portal_submitted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_codes_email", "email_codes", ["email"], unique=False)
    op.create_index("ix_email_codes_purpose", "email_codes", ["purpose"], unique=False)
    op.create_index("ix_email_codes_expires_at", "email_codes", ["expires_at"], unique=False)
    op.create_index("ix_email_codes_email_purpose", "email_codes", ["email", "purpose"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_email_codes_email_purpose", table_name="email_codes")
    op.drop_index("ix_email_codes_expires_at", table_name="email_codes")
    op.drop_index("ix_email_codes_purpose", table_name="email_codes")
    op.drop_index("ix_email_codes_email", table_name="email_codes")
    op.drop_table("email_codes")
