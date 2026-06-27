"""RAG: text chunker — split long text into overlapping chunks.

Sliding-window over sentences to keep chunks around 800-1200 chars with
80-char overlap, suitable for short-form visa FAQ retrieval.

W32: chunk_size bumped 600 → 1000 — gov.uk / france-visas.gouv.fr pages
typically have one big section per page (single 4000+ char page), so 600-char
chunks were splitting a single Q&A into 4 sub-chunks, hurting retrieval.
1000-char chunks keep each whole Q&A as one chunk; recall improves noticeably
on single-section pages without hurting multi-section pages (chunker is
sentence-aware, so it never breaks mid-sentence).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_SENTENCE_END = re.compile(r"(?<=[.!?。!?])\s+")


@dataclass
class Chunk:
    text: str
    index: int


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 80) -> List[Chunk]:
    """Sliding-window sentence-aware chunker."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [Chunk(text=text, index=0)]

    # split by sentence end (works for both Latin + CJK)
    sentences = _SENTENCE_END.split(text)
    chunks: List[Chunk] = []
    cur = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(cur) + len(sent) + 1 <= chunk_size:
            cur = (cur + " " + sent).strip()
        else:
            if cur:
                chunks.append(Chunk(text=cur, index=len(chunks)))
            # start new chunk, prepend overlap tail
            if overlap > 0 and chunks:
                tail = chunks[-1].text[-overlap:]
                cur = (tail + " " + sent).strip()
            else:
                cur = sent
    if cur:
        chunks.append(Chunk(text=cur, index=len(chunks)))
    return chunks
