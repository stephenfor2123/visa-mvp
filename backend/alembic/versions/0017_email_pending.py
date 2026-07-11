"""Add ``email_pending`` column to users (W1 email change flow).

Revision ID: 0017_email_pending
Revises: 0016_applicants
Create Date: 2026-07-06 17:00:00.000000

Holds the *target* email while a change is pending verification. The column
is nullable — populated on POST /profile/email/change-request, cleared on
confirm/cancel. NULL means no pending change.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0017_email_pending"
down_revision = "0016_applicants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email_pending", sa.String(length=120), nullable=True))
        batch_op.create_index("ix_users_email_pending", ["email_pending"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_email_pending")
        batch_op.drop_column("email_pending")
