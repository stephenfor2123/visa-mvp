"""Add users.password_changed_at for JWT invalidation after credential change

Revision ID: 0020_password_changed_at
Revises: 0019_ds160
Create Date: 2026-07-11 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0020_password_changed_at"
down_revision = "0019_ds160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
