"""RAG: text embedder.

We avoid heavyweight deps (sentence-transformers, openai). The embedder is a
deterministic hashed bag-of-words projection: each token contributes to a
fixed-dim vector via signed hashing. The result is a dense, comparable
representation that captures token overlap without semantic meaning. Good
enough for an MVP "official info FAQ" retriever where exact keyword match
matters more than paraphrase robustness.

Trade-off: cheap, deterministic, dependency-free. Trade in semantic recall
for predictable, audit-friendly embeddings.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import List

DEFAULT_DIM = 128
_TOKEN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


def _hash_token(token: str, dim: int) -> tuple[int, float]:
    """Hash a token to (index, sign) — index in [0, dim), sign in {-1, +1}."""
    h = hashlib.md5(token.encode("utf-8")).digest()
    # first 4 bytes → uint32 → index
    idx = int.from_bytes(h[:4], "little") % dim
    # next byte → parity → sign
    sign = 1.0 if (h[4] & 1) else -1.0
    return idx, sign


def embed(text: str, dim: int = DEFAULT_DIM) -> List[float]:
    """Compute a L2-normalized embedding for ``text``."""
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dim
    vec = [0.0] * dim
    for tok in tokens:
        idx, sign = _hash_token(tok, dim)
        vec[idx] += sign
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity — assumes both are L2-normalized (then it's just dot)."""
    if len(a) != len(b) or not a:
        return 0.0
    return sum(x * y for x, y in zip(a, b))
