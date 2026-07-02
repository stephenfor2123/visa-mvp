"""RAG: data source (a webpage or curated content) and chunks.

A Source is a URL we periodically refresh; a Chunk is a piece of text
extracted from a Source, embedded as a vector, and stored for retrieval.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RagSource(Base):
    """An information source (URL or curated content)."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
