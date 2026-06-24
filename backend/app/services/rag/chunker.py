"""RAG: text chunker — split long text into overlapping chunks.

Sliding-window over sentences to keep chunks around 400-800 chars with
80-char overlap, suitable for short-form visa FAQ retrieval.
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


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 80) -> List[Chunk]:
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
