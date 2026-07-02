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
down_revision = "0012_i18n_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # rag_source.language
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

    # rag_chunk.language (denormalized from rag_source for cheap filtering)
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

    # Backfill safety: explicitly set 'zh-CN' for any pre-existing rows in
    # case server_default isn't applied on SQLite-style backends. This is a
    # no-op on Postgres because the server_default already populated the
    # column above, but kept for defensive portability.
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE rag_source SET language = 'zh-CN' WHERE language IS NULL"))
    bind.execute(sa.text("UPDATE rag_chunk SET language = 'zh-CN' WHERE language IS NULL"))


def downgrade() -> None:
    op.drop_index("idx_rag_chunk_source_lang", table_name="rag_chunk")
    op.drop_column("rag_chunk", "language")

    op.drop_index("idx_rag_source_country_lang", table_name="rag_source")
    op.drop_column("rag_source", "language")