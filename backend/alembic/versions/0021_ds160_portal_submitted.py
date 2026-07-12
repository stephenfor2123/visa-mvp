"""Add orders.ds160_portal_submitted_at — user confirmed DS-160 on ceac.state.gov

Revision ID: 0021_ds160_portal_submitted
Revises: 0020_password_changed_at
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_ds160_portal_submitted"
down_revision = "0020_password_changed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "ds160_portal_submitted_at",
            sa.DateTime(),
            nullable=True,
            comment="User confirmed DS-160 submitted on ceac.state.gov (via extension)",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "ds160_portal_submitted_at")
