"""English-authoritative RAG: add metadata + RagTranslation cache.

W31+ design:
  - Retrieval always runs against the English chunk set
    (language='en' filter).
  - The canonical (English) content is the single source of truth;
    every non-English display string is cached under
    (content_hash, target_lang).
  - When the English text changes, content_hash changes, and the
    RagTranslation cache is automatically stale — the next
    retrieval misses and re-translates.

Schema changes
--------------
rag_chunk (add columns, all nullable / default-safe so the migration
  applies to the existing table without backfill):
  - topic           VARCHAR(32)  NOT NULL DEFAULT '*'
  - visa_type       VARCHAR(32)  NOT NULL DEFAULT '*'
  - effective_date  DATE         NULL
  - source_url      VARCHAR(512) NULL
  - content_hash    VARCHAR(40)  NOT NULL DEFAULT ''
  - Composite index on (language, source_id, topic) to keep the
    "English only" retrieval narrow and cheap.

rag_translation (new table):
  - source_hash     VARCHAR(40)  -- SHA-1 of canonical English text
  - target_lang     VARCHAR(8)
  - kind            VARCHAR(32)  -- 'chunk' | 'answer' | 'finding_explain'
  - translated_text TEXT
  - ref_id          INTEGER NULL
  - translated_at   DATETIME
  - UNIQUE (source_hash, target_lang, kind) for O(1) cache hits.

The migration is fully reversible (downgrade() drops the new table
and the added columns in reverse order).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0015_rag_english_authoritative"
down_revision = "0014_rag_language"
branch_labels = ("rag_english",)
depends_on = None


def _hash_content_sql() -> sa.text:  # noqa: D401 — kept for reference only
    """SQL helper retained for documentation. The actual backfill below uses
    Python hashing because SQLite has no built-in sha1().
    """
    return sa.text(
        "UPDATE rag_chunk SET content_hash = sha1(content) "
        "WHERE content_hash = '' OR content_hash IS NULL"
    )


def upgrade() -> None:
    # ---- rag_chunk: add metadata columns + composite index -----------------
    op.add_column(
        "rag_chunk",
        sa.Column("topic", sa.String(length=32), nullable=False, server_default="*"),
    )
    op.add_column(
        "rag_chunk",
        sa.Column("visa_type", sa.String(length=32), nullable=False, server_default="*"),
    )
    op.add_column(
        "rag_chunk",
        sa.Column("effective_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "rag_chunk",
        sa.Column("source_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "rag_chunk",
        sa.Column("content_hash", sa.String(length=40), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_rag_chunk_topic",
        "rag_chunk",
        ["topic"],
        unique=False,
    )
    op.create_index(
        "ix_rag_chunk_visa_type",
        "rag_chunk",
        ["visa_type"],
        unique=False,
    )
    op.create_index(
        "ix_rag_chunk_content_hash",
        "rag_chunk",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_rag_chunk_lang_country_topic",
        "rag_chunk",
        ["language", "source_id", "topic"],
        unique=False,
    )
    # Backfill content_hash for legacy rows that were inserted before the
    # column existed. Done in Python because SQLite doesn't ship sha1()
    # as a built-in (we'd need to enable the crypto extension), and the
    # Python path is portable across all backends. New rows are hashed
    # on save by RagChunk.compute_content_hash().
    import hashlib
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, content FROM rag_chunk WHERE content_hash = '' OR content_hash IS NULL")
    ).fetchall()
    for row_id, content in rows:
        digest = hashlib.sha1(content.encode("utf-8")).hexdigest()
        conn.execute(
            sa.text("UPDATE rag_chunk SET content_hash = :h WHERE id = :i"),
            {"h": digest, "i": row_id},
        )

    # ---- rag_translation: new cache table ---------------------------------
    op.create_table(
        "rag_translation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_hash", sa.String(length=40), nullable=False),
        sa.Column("target_lang", sa.String(length=8), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="chunk"),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column(
            "translated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_rag_translation_source_hash",
        "rag_translation",
        ["source_hash"],
        unique=False,
    )
    op.create_index(
        "ix_rag_translation_target_lang",
        "rag_translation",
        ["target_lang"],
        unique=False,
    )
    op.create_index(
        "ux_rag_translation_lookup",
        "rag_translation",
        ["source_hash", "target_lang", "kind"],
        unique=True,
    )


def downgrade() -> None:
    # Inverse of upgrade — drop the new table first, then strip the new
    # columns + indexes off rag_chunk in the reverse order they were added.
    op.drop_index("ux_rag_translation_lookup", table_name="rag_translation")
    op.drop_index("ix_rag_translation_target_lang", table_name="rag_translation")
    op.drop_index("ix_rag_translation_source_hash", table_name="rag_translation")
    op.drop_table("rag_translation")

    op.drop_index("ix_rag_chunk_lang_country_topic", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_content_hash", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_visa_type", table_name="rag_chunk")
    op.drop_index("ix_rag_chunk_topic", table_name="rag_chunk")
    op.drop_column("rag_chunk", "content_hash")
    op.drop_column("rag_chunk", "source_url")
    op.drop_column("rag_chunk", "effective_date")
    op.drop_column("rag_chunk", "visa_type")
    op.drop_column("rag_chunk", "topic")
