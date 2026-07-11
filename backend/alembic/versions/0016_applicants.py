"""Add ``applicants`` table — W1 personal applicant profile library.

Revision ID: 0016_applicants
Revises: 0015_rag_english_authoritative
Create Date: 2026-07-06 16:55:00.000000

A user can have multiple applicants (e.g. parent adding children). Each
applicant has a (surname, given_name) and a passport_no. The
(surname, given_name) pair is unique per user to prevent duplicates.

Schema:
  - id PK
  - user_id FK -> users.id (CASCADE on delete)
  - surname VARCHAR(64) NOT NULL
  - given_name VARCHAR(64) NOT NULL
  - passport_no VARCHAR(32) NOT NULL (indexed)
  - created_at, updated_at

Constraint:
  - UNIQUE (user_id, surname, given_name)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0016_applicants"
down_revision = "0015_rag_english_authoritative"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applicants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("surname", sa.String(length=64), nullable=False),
        sa.Column("given_name", sa.String(length=64), nullable=False),
        sa.Column("passport_no", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.UniqueConstraint("user_id", "surname", "given_name", name="uq_applicant_user_name"),
    )
    op.create_index("ix_applicants_user_id", "applicants", ["user_id"])
    op.create_index("ix_applicants_passport_no", "applicants", ["passport_no"])


def downgrade() -> None:
    op.drop_index("ix_applicants_passport_no", table_name="applicants")
    op.drop_index("ix_applicants_user_id", table_name="applicants")
    op.drop_table("applicants")
