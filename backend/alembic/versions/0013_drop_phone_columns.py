"""Drop phone / SMS columns from users table.

Revision ID: 0013_drop_phone_columns
Revises: 0012_i18n_overrides
Create Date: 2026-07-01 00:00:00.000000

- users: drop phone, phone_country, mfa_phone, mfa_phone_country
- sms_codes: drop entire table
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0013_drop_phone_columns"
down_revision = "0012_i18n_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop sms_codes table entirely
    op.drop_table("sms_codes")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_phone")
        batch_op.drop_column("phone")
        batch_op.drop_column("phone_country")
        batch_op.drop_column("mfa_phone")
        batch_op.drop_column("mfa_phone_country")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("mfa_phone_country", sa.String(8), nullable=True))
        batch_op.add_column(sa.Column("mfa_phone", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("phone_country", sa.String(8), nullable=True))
        batch_op.add_column(sa.Column("phone", sa.String(32), nullable=True))
        batch_op.create_index("ix_users_phone", ["phone"])

    op.create_table(
        "sms_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(32), nullable=False, index=True),
        sa.Column("phone_country", sa.String(8), nullable=False, server_default="+86"),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
