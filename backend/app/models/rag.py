"""RAG: data source (a webpage or curated content) and chunks.

A Source is a URL we periodically refresh; a Chunk is a piece of text
extracted from a Source, embedded as a vector, and stored for retrieval.

W31+: English-authoritative design
  - Retrieval always runs against the English chunk set (``language='en'``).
  - User-language display is derived on demand via the RagTranslation cache.
  - ``content_hash`` lets the cache invalidate automatically when the
    English source text changes.
  - ``topic`` / ``visa_type`` / ``effective_date`` / ``source_url`` let
    callers filter precisely and cite the original policy.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RagSource(Base):
    """An information source (a URL or curated content)."""

    __tablename__ = "rag_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="zh-CN", index=True)
    url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="web")  # web | curated
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_refresh_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # ok | error
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ---- W62+: 内容审核流程字段 ----
    # last_content_hash = SHA-1 of concatenated chunks content (代表"当前在
    # 用户面前展示的版本"的指纹)。refresh 时算新 hash,跟它对比判断变没变。
    last_content_hash: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True, index=True
    )
    # review_status: synced (无待审) | pending_review (snapshot 等审核)
    # | approved (刚通过) | rejected (拒绝保留旧版) | force_applied
    # 每次 refresh 后默认 pending_review;approve/reject 改状态。
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="synced", index=True
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class RagChunk(Base):
    """A text chunk from a source, with its embedding vector stored as JSON."""

    __tablename__ = "rag_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of floats
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="zh-CN")

    # ---- W31+: English-authoritative retrieval metadata --------------------
    # ``topic`` is the canonical chunk category: 'materials' | 'fees' | 'refusal'
    # | 'financial' | 'overview' | 'policy' | '*'. Default '*' for legacy rows
    # that we have not yet re-categorized.
    topic: Mapped[str] = mapped_column(String(32), nullable=False, default="*", index=True)
    # ``visa_type`` narrows by visa class: 'tourist' | 'business' | 'student' |
    # 'work' | '*'. '*' = applies to all types in this destination.
    visa_type: Mapped[str] = mapped_column(String(32), nullable=False, default="*", index=True)
    # ``effective_date`` marks when this policy was/is in force; null = unknown
    # (legacy). The retriever surfaces "may be outdated" to the UI when null.
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # ``source_url`` lives on the chunk (not just the source) so individual
    # policy sections can cite a specific page anchor or PDF page number.
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # ``content_hash`` is the SHA-1 of the canonical (English) text. The
    # RagTranslation cache is keyed by this hash; when the English text
    # changes, the cache invalidates automatically and we re-translate.
    content_hash: Mapped[str] = mapped_column(String(40), nullable=False, default="", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_rag_chunk_lang_country_topic", "language", "source_id", "topic"),
    )

    def compute_content_hash(self) -> str:
        """Return SHA-1 hex digest of the English text. Idempotent; safe to
        call on every save so the column stays consistent with `content`.
        """
        return hashlib.sha1(self.content.encode("utf-8")).hexdigest()


class RagTranslation(Base):
    """Translation cache for non-English display strings.

    Keyed by (source_hash, target_lang). When the canonical English text
    changes (its hash changes), the cached translation is automatically
    ignored and re-fetched. This is the single fact-source guarantee.
    """

    __tablename__ = "rag_translation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # SHA-1 of the English text being translated (RagChunk.content_hash, or
    # a synthetic hash of an answer body keyed by answer_id).
    source_hash: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # ISO code of the target language: 'zh-CN' | 'en' | 'id' | 'vi'.
    target_lang: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    # Where the text came from: 'chunk' | 'answer' | 'finding_explain'.
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="chunk")
    # The translated text.
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional reference back to the row being translated (e.g. chunk id).
    ref_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    translated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ux_rag_translation_lookup", "source_hash", "target_lang", "kind", unique=True),
    )


# --------------------------------------------------------------------------- #
# W62+: 内容审核快照                                                          #
# --------------------------------------------------------------------------- #
class RagReviewSnapshot(Base):
    """A pending "next version" of a RAG source, waiting for admin approval.

    refresh_source() 抓完 web/curated 内容后,先切好 chunks 存到这张表,不直接
    替换 RagChunk。admin 在 /admin/rag-review 看到 pending_review 的 snapshot,
    approve 后才把内容写回 RagSource.last_content_hash + 替换 RagChunk,
    并把对应旧 hash 的 RagTranslation 缓存失效。

    expires_at 7 天后自动作废 (cleanup task 清理)。
    """

    __tablename__ = "rag_review_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # SHA-1 of concatenated new chunks content. approve 时写回
    # RagSource.last_content_hash;reject 时丢弃。
    content_hash: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # 抓到的原始文本 (web: crawler 输出;curated: 内置文)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 切好的 chunks (JSON array,每元素 {chunk_index, content}) —— 还没落库
    chunks_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Diff 摘要: {added: [...], removed: [...], changed: [{chunk_index, old, new}]}
    diff_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 元信息:抓取时间 / extractor / status / error
    fetch_meta_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # approve/reject 时填的
    decision: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # approved | rejected
    decided_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # 同一 source 只允许一个 "open" snapshot (没 decision 的)。
        # MySQL/SQLite 都支持 partial unique index 的近似:用 status 字段配合
        # 程序层去重。这里先用普通 index,cleanup 时按 expires_at 清理。
        Index("ix_rag_snapshot_source_decision", "source_id", "decision"),
    )
