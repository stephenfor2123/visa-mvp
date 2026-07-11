"""RAG: top-k retriever over stored chunks.

Retrieval is in-memory (load all chunks for the country, score by hybrid
embedding + keyword, return top-k). This is fine for MVP scale (hundreds of
chunks per country). For larger scale, swap in a vector DB (Qdrant / pgvector)
— the interface stays the same.

W31: hybrid search (embedding cosine + BM25-lite keyword) + MMR dedup.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagChunk, RagSource
from app.services.rag.embedder import _content_tokens, cosine_sim, embed, keyword_score


@dataclass
class RetrievedChunk:
    chunk_id: int
    source_id: int
    source_name: str
    source_url: Optional[str]
    chunk_index: int
    text: str
    score: float
    # W31: diagnostic breakdown
    embedding_score: float = 0.0
    keyword_score: float = 0.0
    matched_keywords: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Scoring config — tuned for short-form visa FAQ                              #
# --------------------------------------------------------------------------- #
# Hybrid weight: how much keyword score contributes vs embedding.
# 0.55 keyword + 0.45 embedding — keyword wins slightly because hash embedder
# is token-level (no synonymy), so keyword overlap is the most reliable signal.
EMBEDDING_WEIGHT = 0.45
KEYWORD_WEIGHT = 0.55


async def retrieve(
    db: AsyncSession,
    *,
    query: str,
    country_code: Optional[str] = None,
    top_k: int = 3,
    min_score: float = 0.05,
    use_mmr: bool = True,
    mmr_lambda: float = 0.7,
    language: str = "en",
) -> List[RetrievedChunk]:
    """Embed query, score all chunks (filtered by country + language), top-k.

    W31: hybrid scoring = EMBEDDING_WEIGHT * embedding_cosine +
                           KEYWORD_WEIGHT * keyword_bm25
    Then applies MMR to dedup near-duplicates in the top-k.

    W47c: ``language`` defaults to ``"en"``. Post-W47c the RAG source of truth
    is English — retrieval runs over English chunks regardless of the user's
    display language. Pass a different ``language`` only when testing legacy
    sources or seeded non-English chunks during the migration window.
    """
    q_vec = embed(query)

    stmt = select(RagChunk, RagSource).join(RagSource, RagChunk.source_id == RagSource.id)
    if country_code:
        stmt = stmt.where(RagSource.country_code == country_code)
    if language:
        stmt = stmt.where(RagSource.language == language)
    stmt = stmt.where(RagSource.enabled.is_(True))

    rows = (await db.execute(stmt)).all()

    # First pass: raw scores per chunk
    raw: List[RetrievedChunk] = []
    # W32: lazy migration — when embed() backend changed (hash 128→256, or
    # semantic 384), old chunk embeddings become dim-mismatched. Re-embed on
    # the fly and persist the new value so this happens at most once per chunk.
    mismatched_chunks: List[RagChunk] = []
    for chunk, source in rows:
        try:
            c_vec = json.loads(chunk.embedding)
        except Exception:
            continue
        if len(c_vec) != len(q_vec):
            mismatched_chunks.append(chunk)
            continue
        emb_score = cosine_sim(q_vec, c_vec)
        kw_score, matched = keyword_score(query, chunk.content)
        # Hybrid blend
        final = EMBEDDING_WEIGHT * emb_score + KEYWORD_WEIGHT * kw_score
        if final < min_score:
            continue
        raw.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                source_id=source.id,
                source_name=source.name,
                # chunk-level source_url takes priority over legacy RagSource.url
                source_url=(chunk.source_url or source.url),
                chunk_index=chunk.chunk_index,
                text=chunk.content,
                score=final,
                embedding_score=emb_score,
                keyword_score=kw_score,
                matched_keywords=matched,
            )
        )

    # W32: process dim-mismatched chunks — re-embed using current backend.
    # Without this, dim migration (e.g. hash 128→256) would silently drop every
    # stored chunk and return 0 results.
    for chunk in mismatched_chunks:
        try:
            new_vec = embed(chunk.content)
            chunk.embedding = json.dumps(new_vec)
            emb_score = cosine_sim(q_vec, new_vec)
            kw_score, matched = keyword_score(query, chunk.content)
            final = EMBEDDING_WEIGHT * emb_score + KEYWORD_WEIGHT * kw_score
            if final < min_score:
                continue
            # resolve source for this chunk
            src_row = next(((s, c) for c, s in rows if c.id == chunk.id), None)
            if not src_row:
                continue
            _chunk, source = src_row
            raw.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    source_id=source.id,
                    source_name=source.name,
                    # chunk-level source_url takes priority over legacy RagSource.url
                    source_url=(chunk.source_url or source.url),
                    chunk_index=chunk.chunk_index,
                    text=chunk.content,
                    score=final,
                    embedding_score=emb_score,
                    keyword_score=kw_score,
                    matched_keywords=matched,
                )
            )
        except Exception:
            continue
    if mismatched_chunks:
        # persist re-embedded chunks in one transaction
        try:
            await db.commit()
        except Exception:
            await db.rollback()

    if not raw:
        return []

    # Sort by hybrid score
    raw.sort(key=lambda r: r.score, reverse=True)

    if not use_mmr:
        return raw[:top_k]

    # W31: MMR (Maximal Marginal Relevance) — penalize chunks too similar to
    # already-selected ones. lambda=0.7 (relevance >> diversity).
    return _mmr_select(raw, top_k=top_k, lambda_=mmr_lambda, q_vec=q_vec)


def _mmr_select(
    candidates: List[RetrievedChunk],
    *,
    top_k: int,
    lambda_: float = 0.7,
    q_vec: Optional[List[float]] = None,
) -> List[RetrievedChunk]:
    """MMR selection — pick top_k with relevance × (1 - λ) + diversity × λ.

    Diversity is measured by token Jaccard (fast, dependency-free, no need to
    decode stored embedding again). For more semantic diversity, decode the
    stored chunk embedding and compute cosine — but for short FAQ chunks,
    Jaccard is good enough.
    """
    if not candidates:
        return []

    def _tokens(text: str) -> Set[str]:
        return set(_content_tokens(text))

    selected: List[RetrievedChunk] = []
    selected_tokens: List[Set[str]] = []

    # first pick: highest score
    first = candidates[0]
    selected.append(first)
    selected_tokens.append(_tokens(first.text))

    while len(selected) < top_k and len(selected) < len(candidates):
        best_idx = -1
        best_mmr = -math.inf
        for i, c in enumerate(candidates):
            if c in selected:
                continue
            # max similarity to any already-selected chunk
            c_toks = _tokens(c.text)
            max_sim = 0.0
            for s_toks in selected_tokens:
                if not c_toks or not s_toks:
                    continue
                inter = len(c_toks & s_toks)
                union = len(c_toks | s_toks)
                if union:
                    jacc = inter / union
                    if jacc > max_sim:
                        max_sim = jacc
            # MMR formula: relevance * lambda + (1 - max_sim) * (1 - lambda)
            mmr = c.score * lambda_ + (1.0 - max_sim) * (1.0 - lambda_)
            if mmr > best_mmr:
                best_mmr = mmr
                best_idx = i
        if best_idx < 0:
            break
        selected.append(candidates[best_idx])
        selected_tokens.append(_tokens(candidates[best_idx].text))

    return selected


def _highlight_terms(text: str, terms: List[str]) -> str:
    """Wrap matched terms in ** for client-side highlight (Markdown-ish)."""
    if not terms:
        return text
    out = text
    # case-insensitive for Latin tokens, exact for CJK
    for t in terms:
        if not t:
            continue
        if any('\u4e00' <= ch <= '\u9fff' for ch in t):
            out = out.replace(t, f"**{t}**")
        else:
            # word-boundary, case-insensitive
            import re as _re
            out = _re.sub(
                _re.escape(t),
                lambda m: f"**{m.group(0)}**",
                out,
                flags=_re.IGNORECASE,
            )
    return out


def generate_answer(query: str, retrieved: List[RetrievedChunk]) -> str:
    """Compose an answer from retrieved chunks (extract + highlight).

    W60: previous version trimmed to first 2 sentences, which truncated
    enumeration-style chunks (e.g. "Required Documents: 1. ... 2. ... 3. ...")
    after the first item. New rule: if the chunk has 3+ numbered items
    (1. / 2. / 3. / 一、 / 1) / etc.) treat it as a list-of-items and return
    the full chunk — that's the entire point of the chunk. Otherwise fall
    back to the original 2-sentence trim for prose-style answers.
    Matched terms are still wrapped in **markdown bold** for UI rendering.
    """
    if not retrieved:
        return (
            "未找到相关官方信息。建议直接联系对应国家移民局或使馆。"
        )
    top = retrieved[0]
    snippet = top.text.strip()
    # W60: count enumeration markers (Western "N." or CJK "N、" / "N)")
    import re as _re
    enum_markers = _re.findall(r"(?:^\s*\d+[\.\)、])|(?:^\s*[一二三四五六七八九十]+、)", snippet, flags=_re.MULTILINE)
    if len(enum_markers) >= 3:
        # enumeration-style chunk — show full content (it's the whole point)
        pass
    else:
        # prose-style — trim to 1-2 sentences for readability (W31 behavior)
        parts = [p for p in snippet.split(". ") if p.strip()]
        snippet = ". ".join(parts[:2]).strip()
        if not snippet.endswith("."):
            snippet += "."
    # W31: highlight matched keywords
    snippet = _highlight_terms(snippet, top.matched_keywords or [])
    src = top.source_name
    if top.source_url:
        src = f"{src} ({top.source_url})"
    return f"{snippet}\n\n（来源：{src}）"


def generate_followups(retrieved: List[RetrievedChunk]) -> List[str]:
    """W31: produce 2-3 follow-up question suggestions from top-3 chunks.

    A simple heuristic: pick a salient noun phrase from each top chunk and
    frame as a follow-up. For visa FAQ, "签证费用 / 签证材料 / 审理时间"
    patterns are good defaults.
    """
    if not retrieved:
        return []
    templates = [
        "{} 签证要哪些材料?",
        "{} 签证多少钱?",
        "{} 签证审理多久?",
    ]
    # try to extract country from first chunk
    text = retrieved[0].text
    country_hint = None
    for kw, code in [
        ("美国", "美国"), ("英国", "英国"), ("申根", "申根"),
        ("澳大利亚", "澳大利亚"), ("澳洲", "澳洲"),
        ("日本", "日本"), ("韩国", "韩国"),
    ]:
        if kw in text:
            country_hint = kw
            break
    if not country_hint:
        country_hint = "这个国家"
    return [t.format(country_hint) for t in templates]

def generate_followups_en(retrieved: List[RetrievedChunk]) -> List[str]:
    """W47c: English-language follow-ups. Replaces `generate_followups` for
    the English-authoritative pipeline — the answer orchestrator translates
    these into the user's display language, so the source must be English.
    """
    if not retrieved:
        return []
    templates = [
        "What documents are required for a {country} visa?",
        "How much does a {country} visa cost?",
        "How long does {country} visa processing take?",
    ]
    text = retrieved[0].text
    country_hint = None
    for kw, name in [
        ("United States", "United States"),
        ("U.S.", "United States"),
        ("Schengen", "Schengen"),
        ("United Kingdom", "United Kingdom"),
        ("UK", "United Kingdom"),
        ("Australia", "Australia"),
    ]:
        if kw in text:
            country_hint = name
            break
    if not country_hint:
        country_hint = "this"
    return [t.format(country=country_hint) for t in templates]
