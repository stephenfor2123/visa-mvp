"""RAG: text embedder.

Two backends, picked at runtime:

  1) SentenceTransformerBackend — real semantic embeddings from
     ``sentence-transformers/paraphrase-multilingual-MiniLM-L6-v2`` (384 dim,
     50+ languages, ~220 MB). Used when ``RAG_USE_SEMANTIC=1`` env var is set
     AND the model can be loaded. Trade-off: better paraphrase / cross-language
     recall, but heavier + first-load takes 1-3s.

  2) HashEmbedder — deterministic hashed bag-of-words projection (256 dim,
     default). Each token contributes to a fixed-dim vector via signed hashing
     using 4 independent hash functions (W32). Cheap, deterministic,
     dependency-free. Used as the default fallback and when the semantic model
     is unavailable (no internet, model not cached).

W32: Hybrid search pairs whichever embedder with keyword_score(). The hash
embedder alone can't tell "签证费用" from "签证费" apart, but the keyword path
catches the overlap. The semantic embedder handles cross-language recall
("美国签证费用" matches an English page about US visa fees).

W32: keyword_score() — lightweight token-overlap scoring that catches near-miss
cases the hash embedder misses. For the semantic embedder, keyword_score is
still useful as a length-aware reranker on top of cosine.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from typing import List, Optional, Set, Tuple

# W32: dim 128 → 256 cuts collision probability ~2x for typical token counts.
# Combined with 4 independent hash functions (W32 below) we get effective
# ~1024-dim equivalent representation at 256-dim storage cost.
DEFAULT_DIM = 256
_TOKEN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
# W31: CJK bi-gram regex for keyword matching.
# Why: Chinese "美国签证费用" is 1 token via [\u4e00-\u9fff]+, but "美国" alone
# in a chunk is also 1 token — they don't match. Standard fix: split CJK runs
# into overlapping 2-char grams ("美国签证费用" → "美国/国签/签证/证费/费用").
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")

# Common stopwords (Chinese + English) — filtered from keyword scoring to
# avoid "the / 是 / 的" dominating the score
_STOPWORDS: Set[str] = {
    "the", "a", "an", "is", "are", "of", "to", "in", "and", "or", "for",
    "是", "的", "了", "在", "和", "与", "或", "我", "你", "他", "她", "它",
    "this", "that", "what", "how", "do", "does", "can", "be",
}

# Optional: jieba for query-side word segmentation (better than bi-gram when
# jieba is installed and jieba_dict initialized for visa domain).
try:
    import jieba  # type: ignore
    _JIEBA_OK = True
except ImportError:
    _JIEBA_OK = False


def _tokenize(text: str) -> List[str]:
    """W31: tokenize Latin as words, CJK as overlapping 2-char grams.

    Latin: "schengen visa" → ["schengen", "visa"]
    CJK:   "美国签证费用" → ["美国", "国签", "签证", "证费", "费用"]

    W32: if jieba is available, prefer jieba's word-level segmentation for
    CJK (avoids spurious overlaps from "国签" bi-gram matching random "国"
    in another chunk). Falls back to bi-gram if jieba isn't installed.
    """
    out: List[str] = []
    for m in _TOKEN.finditer(text or ""):
        s = m.group(0)
        if all('\u4e00' <= ch <= '\u9fff' for ch in s):
            if len(s) == 1:
                out.append(s.lower())
            elif _JIEBA_OK and len(s) >= 4:
                # jieba seg on long CJK runs gives cleaner tokens
                for w in jieba.cut(s):
                    w = w.strip().lower()
                    if not w:
                        continue
                    if len(w) >= 2:
                        out.append(w)
                    if len(w) == 1:
                        out.append(w)
                # also keep bi-grams as a fallback for short / ambiguous cases
                for i in range(len(s) - 1):
                    out.append(s[i:i + 2].lower())
                out.append(s.lower())
            else:
                for i in range(len(s) - 1):
                    out.append(s[i:i + 2].lower())
                out.append(s.lower())
        else:
            out.append(s.lower())
    return out


def _hash_token(token: str, dim: int) -> List[Tuple[int, float]]:
    """Hash a token to a list of (index, sign) — W32 multi-hash for less collision.

    Instead of a single md5 → 1 dim cell, we use 4 independent hash functions
    (different salts on md5) so each token touches 4 cells. Effective unique
    slots ~ 4 * dim for collision avoidance, while keeping storage at dim.
    """
    h = hashlib.md5(token.encode("utf-8")).digest()
    out: List[Tuple[int, float]] = []
    # 4 independent hashes: each takes 4 bytes for idx + 1 byte for sign
    for k in range(4):
        start = (k * 5) % (len(h) - 5)
        idx = int.from_bytes(h[start:start + 4], "little") % dim
        sign = 1.0 if (h[start + 4] & 1) else -1.0
        out.append((idx, sign))
    return out


# --------------------------------------------------------------------------- #
# W32: Semantic embedder backend (sentence-transformers). Lazy-loaded.            #
# --------------------------------------------------------------------------- #
_SEMANTIC_MODEL = None
_SEMANTIC_DIM: Optional[int] = None
_SEMANTIC_TRIED = False
_SEMANTIC_ERROR: Optional[str] = None


def _try_load_semantic() -> bool:
    """Attempt to load the sentence-transformers model. Sets module-level
    ``_SEMANTIC_MODEL`` on success. Returns True if loaded, False otherwise.

    Gated by ``RAG_USE_SEMANTIC=1`` env var. If not set, returns False without
    trying to load (no startup cost). If set but model can't be loaded (HF
    auth required, no internet), logs the error and returns False.
    """
    global _SEMANTIC_MODEL, _SEMANTIC_DIM, _SEMANTIC_TRIED, _SEMANTIC_ERROR
    if not os.environ.get("RAG_USE_SEMANTIC", "").strip() == "1":
        return False
    if _SEMANTIC_TRIED:
        return _SEMANTIC_MODEL is not None
    _SEMANTIC_TRIED = True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L6-v2"
        )
        _SEMANTIC_MODEL = model
        _SEMANTIC_DIM = model.get_sentence_embedding_dimension()
        return True
    except Exception as e:  # noqa: BLE001
        _SEMANTIC_ERROR = str(e)[:200]
        return False


def embed(text: str, dim: int = DEFAULT_DIM) -> List[float]:
    """Compute an embedding for ``text``.

    Backend selection (in order):
      1. If sentence-transformers model is loadable → use it (384-dim).
      2. Otherwise → hash embedder (256-dim).

    Both outputs are L2-normalized so cosine == dot product.
    """
    if _try_load_semantic():
        assert _SEMANTIC_MODEL is not None
        vec = _SEMANTIC_MODEL.encode(text or "", normalize_embeddings=True)
        return [float(x) for x in vec]

    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dim
    vec = [0.0] * dim
    for tok in tokens:
        for idx, sign in _hash_token(tok, dim):
            vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity — assumes both are L2-normalized (then it's just dot)."""
    if len(a) != len(b) or not a:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def get_embedder_info() -> dict:
    """Diagnostic: which backend is in use, dim, last error."""
    if _try_load_semantic():
        return {"backend": "semantic", "dim": _SEMANTIC_DIM}
    return {
        "backend": "hash",
        "dim": DEFAULT_DIM,
        "semantic_error": _SEMANTIC_ERROR,
    }


# --------------------------------------------------------------------------- #
# W31: keyword score (BM25-light) — catches near-miss the hash embedder misses   #
# --------------------------------------------------------------------------- #
def _content_tokens(text: str) -> List[str]:
    """Tokens with stopwords filtered (used for keyword scoring only)."""
    return [t for t in _tokenize(text) if t not in _STOPWORDS and len(t) >= 2]


def keyword_score(query: str, text: str) -> Tuple[float, List[str]]:
    """Token-overlap score (BM25-lite), returns (score_in_0_1, matched_tokens).

    Uses sub-linear TF saturation + IDF-ish weight via collection-level rarity.
    For our small chunk collection (hundreds of chunks per country), the
    collection-level IDF is computed on-the-fly per query against the chunks
    passed to retriever.retrieve() — see retriever.retrieve() for the
    full hybrid scoring path.

    This standalone function provides the per-(query, text) component.
    """
    if not query or not text:
        return 0.0, []
    q_tokens = _content_tokens(query)
    t_tokens = _content_tokens(text)
    if not q_tokens or not t_tokens:
        return 0.0, []
    tf = Counter(t_tokens)
    matched = [tok for tok in q_tokens if tok in tf]
    if not matched:
        return 0.0, []
    # sub-linear TF: 1 + log(tf) capped
    score = 0.0
    seen = set()
    for tok in matched:
        if tok in seen:
            continue
        seen.add(tok)
        # length bonus: longer tokens (more specific terms) weighted higher
        length_bonus = min(1.5, 1.0 + (len(tok) - 2) * 0.1)
        # sub-linear TF saturation
        tf_score = 1.0 + math.log(tf[tok]) if tf[tok] > 0 else 0.0
        score += length_bonus * tf_score
    # normalize: divide by sqrt(query_len * text_len) so longer texts don't
    # dominate just by being long
    norm = math.sqrt(len(q_tokens) * len(t_tokens)) or 1.0
    return min(1.0, score / norm), matched
