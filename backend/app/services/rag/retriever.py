"""RAG: top-k retriever over stored chunks.

Retrieval is in-memory (load all chunks for the country, score by cosine,
return top-k). This is fine for MVP scale (hundreds of chunks per country).
For larger scale, swap in a vector DB (Qdrant / pgvector) — the interface
stays the same.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagChunk, RagSource
from app.services.rag.embedder import cosine_sim, embed


@dataclass
class RetrievedChunk:
    chunk_id: int
    source_id: int
    source_name: str
    source_url: Optional[str]
    chunk_index: int
    text: str
    score: float


async def retrieve(
    db: AsyncSession,
    *,
    query: str,
    country_code: Optional[str] = None,
    top_k: int = 3,
    min_score: float = 0.05,
) -> List[RetrievedChunk]:
    """Embed query, score all chunks (filtered by country if given), top-k."""
    q_vec = embed(query)

    stmt = select(RagChunk, RagSource).join(RagSource, RagChunk.source_id == RagSource.id)
    if country_code:
        stmt = stmt.where(RagSource.country_code == country_code)
    stmt = stmt.where(RagSource.enabled.is_(True))

    rows = (await db.execute(stmt)).all()

    scored: List[RetrievedChunk] = []
    for chunk, source in rows:
        try:
            c_vec = json.loads(chunk.embedding)
        except Exception:
            continue
        if len(c_vec) != len(q_vec):
            continue
        score = cosine_sim(q_vec, c_vec)
        if score < min_score:
            continue
        scored.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                source_id=source.id,
                source_name=source.name,
                source_url=source.url,
                chunk_index=chunk.chunk_index,
                text=chunk.content,
                score=score,
            )
        )
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]


def generate_answer(query: str, retrieved: List[RetrievedChunk]) -> str:
    """Compose an answer from retrieved chunks.

    Without an LLM in the loop, the answer is the top-1 chunk with attribution.
    This is the "extract" RAG pattern, not "abstract" — accurate for FAQ-style
    content where the official phrasing is what users actually need.
    """
    if not retrieved:
        return (
            "未找到相关官方信息。建议直接联系对应国家移民局或使馆。"
        )
    top = retrieved[0]
    snippet = top.text.strip()
    # trim to 1-2 sentences for readability
    parts = [p for p in snippet.split(". ") if p.strip()]
    snippet = ". ".join(parts[:2]).strip()
    if not snippet.endswith("."):
        snippet += "."
    src = top.source_name
    if top.source_url:
        src = f"{src} ({top.source_url})"
    return f"{snippet}\n\n（来源：{src}）"
