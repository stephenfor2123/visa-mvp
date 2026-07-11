"""RAG: translation cache + thin LLM wrapper.

Architecture (post-W47c — English-authoritative RAG):

  - RAG source of truth is English: chunks are stored in English, retrieval
    runs over English chunks.
  - User-facing surfaces (answers, snippets, follow-up suggestions) are
    translated from English to the user's language on demand, with a
    `RagTranslation` cache table keyed by `(source_hash, target_lang, kind)`.
  - `source_hash` is the SHA-1 of the *English source text*. If the English
    chunk changes, the hash changes, all cached translations are invalidated
    together. Single-source-of-truth invariant.

Translation kind is one of:

  - ``"query"``   — translating the user's question into English for retrieval
                    (input: user_lang text, output: English)
  - ``"answer"``  — translating the generated English answer/snippet into the
                    user's language
  - ``"snippet"`` — translating raw chunk text (used to display a chunk in the
                    user's language without re-running the generator)

Failure modes (graceful, all log):

  - LLM not configured / network error → return the source text (English
    fallback). User still gets information; the UI just shows it in English.
  - Cache lookup miss but DB write fails → log warning, still return translated
    text. We never fail the request because the cache layer had a hiccup.

We intentionally do NOT translate:

  - Field names, country codes, filenames (DS-160, MRV, EVUS), proper nouns.
    The prompt explicitly tells the LLM to keep these intact.
  - Source URLs (technical identifier).
  - Numeric codes (visa numbers, fee amounts in source currency).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RagTranslation

_log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Public surface                                                              #
# --------------------------------------------------------------------------- #
# Languages we render in. Anything else falls through to English.
SUPPORTED_LANGS = {"zh-CN", "en", "id", "vi"}


def is_english(lang: Optional[str]) -> bool:
    """True when the user already reads English — callers can skip translation."""
    if not lang:
        return True
    return lang.strip().lower().startswith("en")


def hash_source(text: str) -> str:
    """Cache key seed: SHA-1 of the English source text. UTF-8 encoded.

    We use SHA-1 here for cache keying only (not for integrity). 40-char hex
    matches ``RagTranslation.source_hash`` column width.
    """
    return hashlib.sha1((text or "").encode("utf-8")).hexdigest()


async def to_english(
    db: AsyncSession,
    query: str,
    source_lang: Optional[str],
) -> str:
    """Translate the user's question into English for retrieval.

    - ``source_lang == "en"`` or empty → return the query unchanged.
    - Cache hit → return stored English.
    - Cache miss → call LLM, persist, return.

    On LLM failure: returns the original query (best-effort English fallback).
    """
    text = (query or "").strip()
    if not text:
        return ""
    # Normalize BCP-47 long tags (id-ID / vi-VN) to short codes so the LLM
    # gets a recognisable source language name.
    source_lang = _short_lang(source_lang)
    if is_english(source_lang):
        return text

    cached = await _get_cached(db, source_hash=hash_source(text), target_lang="en", kind="query")
    if cached is not None:
        return cached

    translated = await _call_llm_translate(text, source_lang or "zh-CN", target="en")
    if not translated:
        # Last-ditch fallback: pass through the original. The English-side
        # retrieval will still try to find English chunks using keyword match.
        return text

    await _put_cached(db, source_hash=hash_source(text), target_lang="en", kind="query", text=translated)
    return translated


async def to_display(
    db: AsyncSession,
    text: str,
    target_lang: Optional[str],
    *,
    kind: str = "answer",
) -> str:
    """Translate English RAG output into the user's language for display.

    - Empty / English-only target → return ``text`` unchanged.
    - Cache hit → return cached translation.
    - Cache miss → call LLM, persist, return.

    On LLM failure: returns the original English text. UI handles English-only
    fallback gracefully (label: "From official source").
    """
    body = (text or "").strip()
    if not body:
        return ""
    # Normalize BCP-47 long tags (id-ID / vi-VN) to short codes (id / vi) so
    # cache keys are consistent and the LLM target name resolves.
    target_lang = _short_lang(target_lang)
    if is_english(target_lang):
        return body

    cached = await _get_cached(db, source_hash=hash_source(body), target_lang=target_lang or "zh-CN", kind=kind)
    if cached is not None:
        return cached

    translated = await _call_llm_translate(body, "en", target=target_lang or "zh-CN")
    if not translated:
        return body

    await _put_cached(
        db,
        source_hash=hash_source(body),
        target_lang=target_lang or "zh-CN",
        kind=kind,
        text=translated,
    )
    return translated


async def to_display_many(
    db: AsyncSession,
    texts: list[str],
    target_lang: Optional[str],
    *,
    kind: str = "snippet",
) -> list[str]:
    """Batch variant of ``to_display`` — same logic per item.

    Used for snippet translation in the /query response where multiple chunks
    need display rendering. Items are processed sequentially because the
    cache layer is a SQLite single-writer; parallelism wouldn't help.
    """
    if is_english(target_lang):
        return list(texts)
    return [await to_display(db, t, target_lang, kind=kind) for t in texts]


# --------------------------------------------------------------------------- #
# Cache layer                                                                 #
# --------------------------------------------------------------------------- #
async def _get_cached(
    db: AsyncSession,
    *,
    source_hash: str,
    target_lang: str,
    kind: str,
) -> Optional[str]:
    stmt = select(RagTranslation.translated_text).where(
        RagTranslation.source_hash == source_hash,
        RagTranslation.target_lang == target_lang,
        RagTranslation.kind == kind,
    )
    row = (await db.execute(stmt)).first()
    return row[0] if row else None


async def _put_cached(
    db: AsyncSession,
    *,
    source_hash: str,
    target_lang: str,
    kind: str,
    text: str,
) -> None:
    """Upsert by unique key. SQLite's ON CONFLICT keeps the DB layer portable."""
    stmt = sqlite_insert(RagTranslation).values(
        source_hash=source_hash,
        target_lang=target_lang,
        kind=kind,
        translated_text=text,
    ).on_conflict_do_update(
        index_elements=["source_hash", "target_lang", "kind"],
        set_={"translated_text": text},
    )
    try:
        await db.execute(stmt)
        await db.commit()
    except IntegrityError as e:
        # Concurrent writer race — extremely rare in MVP SQLite. Roll back
        # and log; the cached row from the other writer is still valid.
        await db.rollback()
        _log.warning("rag translation cache write race: %s", e)
    except Exception as e:  # noqa: BLE001
        await db.rollback()
        _log.warning("rag translation cache write failed: %s", e)


# --------------------------------------------------------------------------- #
# LLM call (translation prompt)                                               #
# --------------------------------------------------------------------------- #
# Per-language system prompt. Naming preserves proper nouns (DS-160, MRV,
# EVUS) and numeric codes. Conservative tone — we are translating government
# text, not paraphrasing it.
SYSTEM_PROMPT_BASE = (
    "You are a precise visa-information translator. Translate the following "
    "official English visa text into {target_name}. "
    "Constraints: (1) keep proper nouns, visa form numbers (DS-160, MRV, "
    "EVUS), currency amounts, country names, and URLs unchanged; "
    "(2) do not summarize, add, or invent information — translate ONLY what "
    "is in the source; (3) preserve the original tone (official / "
    "informational); (4) never insert file extensions (e.g. .docx, .pdf), "
    "file names, or named entities that do not appear in the source; "
    "(5) output the translation only, with no preamble or explanation."
)

_LANG_NAMES = {
    "zh-CN": "Simplified Chinese (zh-CN)",
    "en": "English",
    "id": "Indonesian (Bahasa Indonesia)",
    "vi": "Vietnamese (tiếng Việt)",
}


def _short_lang(lang: Optional[str]) -> str:
    """Normalize BCP-47 / browser tags to the short codes used internally.

    Frontend `vue-i18n` emits ``id-ID`` / ``vi-VN`` (BCP-47 long tags) when the
    user picks Indonesian or Vietnamese in the language switcher. Our cache key
    and ``_LANG_NAMES`` lookup table only know short codes (``id`` / ``vi``).
    Without this helper, an incoming ``id-ID`` falls through ``_LANG_NAMES.get``
    and gets passed to the LLM as a literal target string — which the LLM
    doesn't recognise as a language, so it returns English (or empty).

    Examples
    --------
    >>> _short_lang("id-ID")
    'id'
    >>> _short_lang("VI-vn")
    'vi'
    >>> _short_lang("en")
    'en'
    >>> _short_lang(None)
    'zh-CN'
    """
    if not lang:
        return "zh-CN"
    s = lang.strip()
    # BCP-47 long tags use '-' as separator: 'id-ID' → 'id', 'zh-Hans-CN' → 'zh'.
    if "-" in s:
        s = s.split("-", 1)[0]
    s = s.lower()
    # "zh" / "zh-cn" / "zh-hans" all map to our canonical "zh-CN".
    if s == "zh":
        return "zh-CN"
    return s


async def _call_llm_translate(text: str, source_lang: str, *, target: str) -> str:
    """Translate via MiniMax; return empty string on any failure.

    Importing the client lazily so this module can be imported even when the
    LLM SDK / api key isn't configured. Returning "" on missing config means
    the caller falls back to passthrough.
    """
    # Normalize BCP-47 tags (id-ID / vi-VN) → short codes (id / vi) before
    # resolving the language name; otherwise the LLM gets a literal "id-ID"
    # which it can't translate.
    target = _short_lang(target)
    target_name = _LANG_NAMES.get(target, target)
    system_prompt = SYSTEM_PROMPT_BASE.format(target_name=target_name)
    user_msg = (
        f"Source language: {source_lang}\n"
        f"Target language: {target_name}\n\n"
        f"Text:\n{text}"
    )
    try:
        # Imported here for the optional-dependency behavior described above.
        from app.services.llm.minimax_client import get_minimax_client
        client = get_minimax_client()
        if not client.configured:
            return ""
        out = await client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,  # very low — translation needs to be deterministic
        )
        return (out or "").strip()
    except Exception as e:  # noqa: BLE001
        _log.warning("rag translate llm call failed (source=%s target=%s): %s", source_lang, target, e)
        return ""
