"""Add W62 content review workflow columns to ``rag_source``.

Revision ID: 0018_rag_review_workflow
Revises: 0017_email_pending
Create Date: 2026-07-07 09:55:00.000000

The W62 spec introduced a content review flow: each ``rag_source`` tracks the
hash of the chunks currently shown to the user (``last_content_hash``), the
review status of the latest pending snapshot (``review_status``), and the
reviewer attribution fields (``reviewed_by`` / ``reviewed_at`` / ``review_note``).

The columns were added to ``app/models/rag.py`` and are read/written by
``app/api/v2/admin_rag.py`` and ``app/services/rag/refresh.py``, but the
matching alembic migration was never generated. Without this migration,
SQLAlchemy queries against ``rag_source`` raise ``OperationalError: no such
column: rag_source.last_content_hash``.

Schema notes
------------
- ``last_content_hash`` is SHA-1 hex (40 chars) of concatenated chunk content.
- ``review_status`` defaults to ``synced`` — pre-existing rows have no pending
  review snapshot, so they remain in the legacy state.
- ``reviewed_by`` references ``users.id`` but we don't enforce FK here to keep
  the migration reversible without touching users-table FKs.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0018_rag_review_workflow"
down_revision = "0017_email_pending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rag_source") as batch_op:
        batch_op.add_column(
            sa.Column("last_content_hash", sa.String(length=40), nullable=True)
        )
        batch_op.create_index(
            "ix_rag_source_last_content_hash", ["last_content_hash"], unique=False
        )
        batch_op.add_column(
            sa.Column(
                "review_status",
                sa.String(length=32),
                nullable=False,
                server_default="synced",
            )
        )
        batch_op.create_index(
            "ix_rag_source_review_status", ["review_status"], unique=False
        )
        batch_op.add_column(sa.Column("reviewed_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("review_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rag_source") as batch_op:
        batch_op.drop_column("review_note")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by")
        batch_op.drop_index("ix_rag_source_review_status")
        batch_op.drop_column("review_status")
        batch_op.drop_index("ix_rag_source_last_content_hash")
        batch_op.drop_column("last_content_hash")