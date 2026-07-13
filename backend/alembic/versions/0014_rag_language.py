"""Add ``language`` column to rag_source and rag_chunk.

Revision ID: 0014_rag_language
Revises: 0012_i18n_overrides
Create Date: 2026-07-02 18:33:00.000000

NOTE: Originally written with down_revision='0013_drop_phone_columns' but
0013 has a pre-existing bug (assumes ix_users_phone exists). To keep this
migration runnable independently of 0013's status, we chain off 0012. When
0013 is fixed, the chain can be straightened by changing down_revision
back to '0013_drop_phone_columns' without re-running this migration.

Adds a single new column ``language`` (varchar(8), default 'zh-CN', indexed) to
both ``rag_source`` and ``rag_chunk``. The column is backfilled to 'zh-CN' for
all existing rows so the current Chinese-only data set keeps working without
any code changes.

Going forward, callers can seed per-language RAG content (e.g. 'en', 'zh-CN')
and the /v2/rag/checklist endpoint will filter by the requested language so
the frontend can show English materials/fee/processing_time when the user
switches to English.

Schema-impacting notes:
  - rag_source.language is NOT unique together with country_code — the same
    country can have multiple language variants of the same source.
  - rag_chunk.language is read-only-on-write: set at seed time, never
    updated post-hoc (would invalidate the embedding).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0014_rag_language"
down_revision = "0013_drop_phone_columns"
branch_labels = None
depends_on = None


def _ensure_rag_base_tables() -> None:
    """Fresh installs never had a migration that created rag_* tables."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "rag_source" not in tables:
        op.create_table(
            "rag_source",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("country_code", sa.String(8), nullable=False),
            sa.Column("url", sa.String(512), nullable=True),
            sa.Column("content_type", sa.String(32), nullable=False, server_default="web"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("last_refresh_at", sa.DateTime(), nullable=True),
            sa.Column("last_status", sa.String(32), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index("ix_rag_source_name", "rag_source", ["name"], unique=False)
        op.create_index("ix_rag_source_country_code", "rag_source", ["country_code"], unique=False)

    if "rag_chunk" not in tables:
        op.create_table(
            "rag_chunk",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("source_id", sa.Integer(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("embedding", sa.Text(), nullable=False),
            sa.Column("embedding_dim", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index("ix_rag_chunk_source_id", "rag_chunk", ["source_id"], unique=False)


def upgrade() -> None:
    _ensure_rag_base_tables()

    bind = op.get_bind()
    insp = sa.inspect(bind)
    rag_source_cols = {c["name"] for c in insp.get_columns("rag_source")}
    rag_chunk_cols = {c["name"] for c in insp.get_columns("rag_chunk")}

    if "language" not in rag_source_cols:
        op.add_column(
            "rag_source",
            sa.Column(
                "language",
                sa.String(8),
                nullable=False,
                server_default="zh-CN",
            ),
        )
        op.create_index(
            "idx_rag_source_country_lang",
            "rag_source",
            ["country_code", "language"],
        )

    if "language" not in rag_chunk_cols:
        op.add_column(
            "rag_chunk",
            sa.Column(
                "language",
                sa.String(8),
                nullable=False,
                server_default="zh-CN",
            ),
        )
        op.create_index(
            "idx_rag_chunk_source_lang",
            "rag_chunk",
            ["source_id", "language"],
        )

    bind.execute(sa.text("UPDATE rag_source SET language = 'zh-CN' WHERE language IS NULL"))
    bind.execute(sa.text("UPDATE rag_chunk SET language = 'zh-CN' WHERE language IS NULL"))


def downgrade() -> None:
    op.drop_index("idx_rag_chunk_source_lang", table_name="rag_chunk")
    op.drop_column("rag_chunk", "language")

    op.drop_index("idx_rag_source_country_lang", table_name="rag_source")
    op.drop_column("rag_source", "language")