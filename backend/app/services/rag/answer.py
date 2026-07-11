"""RAG: answer orchestration (post-W47c).

English-authoritative flow:

  1. ``translate_user_query`` — if the user asks in zh-CN/id/vi, translate the
     question into English first (cache: ``RagTranslation kind=query``).
  2. ``retrieve`` over English chunks (existing retriever with ``language='en'``
     filter — see retriever.py).
  3. ``generate_answer_en`` extracts a short English snippet from the top-1
     chunk (with match-highlighting).
  4. ``translate_answer`` renders the snippet into the user's language (cache:
     ``RagTranslation kind=answer``).

This keeps a single RAG semantic per country (one retrieval semantic, one
generator prompt) while rendering in the user's language.

The orchestrator is intentionally small — it composes existing pieces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rag import translate as rag_translate
from app.services.rag.retriever import (
    RetrievedChunk,
    generate_answer as _generate_answer_en,
    generate_followups_en as _generate_followups_en,
    retrieve,
)


@dataclass
class RagAnswer:
    """End-to-end answer in the user's language, with debug data."""

    query: str              # the user-facing query (translated into their lang: same as input)
    answer: str             # answer snippet rendered in user_lang
    chunks: List[RetrievedChunk] = field(default_factory=list)
    followups: List[str] = field(default_factory=list)
    # Debug fields (only populated when caller asks)
    en_query: Optional[str] = None
    en_answer: Optional[str] = None
    user_lang: Optional[str] = None


async def answer_user_query(
    db: AsyncSession,
    *,
    query: str,
    country_code: Optional[str] = None,
    user_lang: Optional[str] = None,
    top_k: int = 3,
    min_score: float = 0.05,
    use_mmr: bool = True,
    debug: bool = False,
) -> RagAnswer:
    """Compose an answer for the user. Language flow handled internally.

    Parameters
    ----------
    query : str
        User's question, in their own language.
    country_code : str, optional
        Limit retrieval to one country (2-3 letter code).
    user_lang : str, optional
        One of ``zh-CN``, ``en``, ``id``, ``vi``. Anything else → no
        translation, English passthrough.
    """
    user_lang = (user_lang or "en").strip()
    src_query = (query or "").strip()

    # 1) Translate the user's question into English for retrieval.
    en_query = await rag_translate.to_english(db, src_query, user_lang)

    # 2) Retrieve over English chunks only. The retriever filters by language
    # internally; country_code narrows the source set further.
    chunks = await retrieve(
        db,
        query=en_query,
        country_code=country_code,
        top_k=top_k,
        min_score=min_score,
        use_mmr=use_mmr,
    )

    # 3) Compose English answer (snippet + source attribution).
    en_answer = _generate_answer_en(en_query, chunks)

    # 4) Render in the user's language. If user_lang is English-ish or empty,
    #    this just returns en_answer unchanged.
    user_answer = await rag_translate.to_display(db, en_answer, user_lang, kind="answer")

    # Follow-up suggestions — also translated.
    en_followups = _generate_followups_en(chunks)
    user_followups: List[str] = []
    if en_followups:
        # Translate them as a list. They are short, so we translate each.
        for f in en_followups:
            rendered = await rag_translate.to_display(db, f, user_lang, kind="snippet")
            user_followups.append(rendered)

    return RagAnswer(
        query=src_query,
        answer=user_answer,
        chunks=chunks,
        followups=user_followups,
        en_query=en_query if debug else None,
        en_answer=en_answer if debug else None,
        user_lang=user_lang if debug else None,
    )
