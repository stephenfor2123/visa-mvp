"""One-shot patcher: add W47c metadata to en/id/vi seed scripts.

Inserts:
  - import hashlib, from datetime import date
  - _TOPIC_BY_INDEX constant
  - COUNTRY_META map at module level
  - in upsert_chunks(): per-chunk topic lookup, visa_type/effective_date/
    source_url from COUNTRY_META, content_hash via SHA-1, persisted alongside.

Idempotent — re-running this patcher is safe (it rewrites in-place but skips
already-patched files: a small marker comment is added at the top).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/Users/apple/Desktop/签证项目_副本/backend/scripts")

LANG = {
    "seed_rag_chunks_en.py": "en",
    "seed_rag_chunks_id.py": "id",
    "seed_rag_chunks_vi.py": "vi",
}

# W47c metadata — maps chunk_index → topic. Same for all countries / languages
# because the chunk layout (0=materials, 1=fees, 2=refusal) is invariant.
TOPIC_BY_INDEX = "TOPIC_BY_INDEX = {0: \"materials\", 1: \"fees\", 2: \"refusal\"}"

# Per-country metadata. effective_date is the date the source content was
# last verified against the official site.
COUNTRY_META = {
    "seed_rag_chunks_en.py": '''COUNTRY_META = {
    "US": ("b1_b2", "2025-09-30", "https://travel.state.gov/content/travel/en/us-visas.html"),
    "GB": ("standard_visitor", "2025-04-09", "https://www.gov.uk/standard-visitor"),
    "AU": ("subclass_600", "2025-07-01", "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"),
    "FR": ("c_short_stay", "2024-06-11", "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"),
}''',
    "seed_rag_chunks_id.py": '''COUNTRY_META = {
    "US": ("b1_b2", "2025-09-30", "https://travel.state.gov/content/travel/en/us-visas.html"),
    "GB": ("standard_visitor", "2025-04-09", "https://www.gov.uk/standard-visitor"),
    "AU": ("subclass_600", "2025-07-01", "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"),
    "FR": ("c_short_stay", "2024-06-11", "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"),
}''',
    "seed_rag_chunks_vi.py": '''COUNTRY_META = {
    "US": ("b1_b2", "2025-09-30", "https://travel.state.gov/content/travel/en/us-visas.html"),
    "GB": ("standard_visitor", "2025-04-09", "https://www.gov.uk/standard-visitor"),
    "AU": ("subclass_600", "2025-07-01", "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"),
    "FR": ("c_short_stay", "2024-06-11", "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"),
}''',
}

PATCH_MARKER = "# W47c METADATA PATCH"


def patch_file(name: str) -> None:
    path = ROOT / name
    src = path.read_text(encoding="utf-8")
    if PATCH_MARKER in src:
        print(f"  {name}: already patched, skipping")
        return

    # 1. Add imports + topic meta + country meta right after the
    # `from app.services.rag.embedder import embed` import line.
    insert_after = "from app.services.rag.embedder import embed\n"
    if insert_after not in src:
        raise SystemExit(f"{name}: anchor not found")
    extra = (
        "import hashlib\n"
        "from datetime import date\n\n\n"
        f"# {PATCH_MARKER.lstrip('# ')}\n"
        f"{TOPIC_BY_INDEX}\n\n"
        f"{COUNTRY_META[name]}\n"
    )
    src = src.replace(insert_after, insert_after + extra, 1)

    # 2. Rewrite upsert_chunks body to compute metadata + content_hash.
    # We replace just the inner loop body for `for c in items:` onward.
    needle = "    items = CHUNKS.get(country_code, [])\n    n = 0\n    for c in items:\n        existing = (await db.execute(\n            select(RagChunk).where(\n                RagChunk.source_id == source_id,\n                RagChunk.chunk_index == c[\"chunk_index\"],\n            )\n        )).scalar_one_or_none()\n        emb = embed(c[\"content\"])\n        if existing:\n            existing.content = c[\"content\"]\n            existing.embedding = json.dumps(emb)\n            existing.embedding_dim = len(emb)\n            existing.language = LANG\n        else:\n            db.add(RagChunk(\n                source_id=source_id,\n                chunk_index=c[\"chunk_index\"],\n                content=c[\"content\"],\n                embedding=json.dumps(emb),\n                embedding_dim=len(emb),\n                language=LANG,\n            ))\n        n += 1\n    return n\n"
    replacement = """    items = CHUNKS.get(country_code, [])
    visa_type, eff_iso, src_url = COUNTRY_META.get(
        country_code,
        ("*", "2025-01-01", None),
    )
    _y, _m, _d = (int(x) for x in eff_iso.split("-"))
    effective_date = date(_y, _m, _d)
    n = 0
    for c in items:
        # Look up existing chunk at this index
        existing = (await db.execute(
            select(RagChunk).where(
                RagChunk.source_id == source_id,
                RagChunk.chunk_index == c["chunk_index"],
            )
        )).scalar_one_or_none()
        emb = embed(c["content"])
        content_hash = hashlib.sha1(c["content"].encode("utf-8")).hexdigest()
        topic = TOPIC_BY_INDEX.get(c["chunk_index"], "overview")
        if existing:
            existing.content = c["content"]
            existing.content_hash = content_hash
            existing.embedding = json.dumps(emb)
            existing.embedding_dim = len(emb)
            existing.language = LANG
            existing.topic = topic
            existing.visa_type = visa_type
            existing.effective_date = effective_date
            existing.source_url = src_url
        else:
            db.add(RagChunk(
                source_id=source_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                content_hash=content_hash,
                embedding=json.dumps(emb),
                embedding_dim=len(emb),
                language=LANG,
                topic=topic,
                visa_type=visa_type,
                effective_date=effective_date,
                source_url=src_url,
            ))
        n += 1
    return n
"""
    if needle not in src:
        raise SystemExit(f"{name}: upsert_chunks needle not found (script may have been edited)")
    src = src.replace(needle, replacement, 1)
    path.write_text(src, encoding="utf-8")
    print(f"  {name}: patched")


if __name__ == "__main__":
    for n in LANG:
        patch_file(n)
    print("done.")
