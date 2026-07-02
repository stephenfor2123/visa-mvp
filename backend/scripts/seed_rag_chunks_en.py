"""Seed curated FAQ chunks for the 4 product-line RagSources (GB/FR/US/AU)
in **English** so the /v2/rag/checklist endpoint can serve English content
when the frontend is on the English locale.

Pairs with seed_rag_chunks.py (which seeds the Chinese variants under
language='zh-CN'). The source rows are upserted so re-running this script is
safe; existing English-language chunks for a (country, chunk_index) pair are
overwritten, existing chunks at other indices are preserved.

Run:  cd backend && python scripts/seed_rag_chunks_en.py
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.rag import RagChunk, RagSource
from app.services.rag.embedder import embed

LANG = "en"

# Per-country curated FAQ chunks — English variants of seed_rag_chunks.py
# content. Same 3-chunk structure (materials / fee+timing / rejection reasons)
# to keep parser parity between languages.
CHUNKS = {
    "US": [
        {
            "chunk_index": 0,
            "content": (
                "US B1/B2 Tourist/Business Visa Required Materials:\n"
                "1. Valid passport (must be valid for at least 6 months beyond your planned departure date)\n"
                "2. DS-160 confirmation page (printed after online submission, with barcode)\n"
                "3. Visa application fee receipt ($160 USD MRV fee)\n"
                "4. One white-background color photo (51mm × 51mm, frontal, no glasses)\n"
                "5. Employment letter or business license copy (with company seal)\n"
                "6. Recent bank statements or deposit certificate (last 3 months recommended)\n"
                "7. Trip itinerary and flight/hotel reservations\n"
                "8. Interview confirmation letter (generated after scheduling the consular appointment)"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "US B1/B2 Visa Fees and Processing Time:\n"
                "Visa Fee: $160 USD (MRV fee), payable online before scheduling the interview.\n"
                "Processing Time: Typically 5-15 business days based on embassy workload; peak seasons (summer, Chinese New Year) may extend to 3-4 weeks.\n"
                "Validity: Usually issued as a 10-year multiple-entry visa (B1/B2 category).\n"
                "Maximum Stay: Determined by the CBP officer at the port of entry, typically not exceeding 6 months per visit.\n"
                "Application Tips: Schedule the interview early, prepare concise and honest answers, organize documents in the requested order."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "US B1/B2 Visa Common Rejection Reasons and Strengthening Documents:\n"
                "Common Rejection: Section 214(b) (presumption of immigration intent) — the single most common refusal reason.\n"
                "Strengthening Documents: Proof of strong ties to home country (property deed, employment letter, household registration), extensive travel history, stable income statements, detailed US trip plan.\n"
                "Interview Tips: State the tourism purpose clearly, keep answers concise and truthful, avoid bringing up immigration-related topics unprompted.\n"
                "First-time Applicants (Blank Passport): Provide more substantial proof of ties to your home country."
            ),
        },
    ],
    "GB": [
        {
            "chunk_index": 0,
            "content": (
                "UK Standard Visitor Visa Required Materials:\n"
                "1. Valid passport (with at least one blank page)\n"
                "2. Online application form (printed after submission, with reference number)\n"
                "3. Tuberculosis (TB) test certificate (valid for 6 months)\n"
                "4. Employment letter or enrollment certificate\n"
                "5. Recent bank statements (last 3 months, showing stable income source)\n"
                "6. Hotel reservations and round-trip flight booking\n"
                "7. Two passport-size white-background photos"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "UK Standard Visitor Visa Fees and Processing Time:\n"
                "Visa Fee: £95 GBP for short-term (6-month) visit visa.\n"
                "Processing Time: Standard service 15 working days; priority service 5 working days; super priority 24 hours.\n"
                "Validity: Up to 6 months multiple entry; long-term (2/5/10 year) visitor visas available at higher fees.\n"
                "TB Test: Must be conducted at a Home Office-approved clinic in China; certificates from other clinics are not accepted."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "UK Visa Common Rejection Reasons:\n"
                "Insufficient financial proof: Low bank balance or unclear source of funds.\n"
                "Weak ties to home country: Cannot demonstrate intent to depart the UK on time (no property, no stable employment).\n"
                "Failed TB test: Active TB patients must complete treatment before applying.\n"
                "Contradictory application info: Travel itinerary does not match hotel/flight bookings.\n"
                "Recommendation: Provide authentic complete documents, reasonable itinerary, and purchase non-refundable flight/hotel bookings (keep payment receipts)."
            ),
        },
    ],
    "AU": [
        {
            "chunk_index": 0,
            "content": (
                "Australia Tourist Visa (Subclass 600) Required Materials:\n"
                "1. Valid passport (color scanned copy)\n"
                "2. Recent passport-size photo\n"
                "3. Identity documents (national ID card, household registration)\n"
                "4. Employment letter or business license\n"
                "5. Recent bank statements (last 3-6 months)\n"
                "6. Travel itinerary and round-trip flight booking\n"
                "7. Hotel reservations or invitation letter from Australian host"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Australia Tourist Visa (Subclass 600) Fees and Processing Time:\n"
                "Visa Fee: AUD $190 (approximately 900 RMB), payable online by credit card.\n"
                "Processing Time: Standard 15-25 working days; peak seasons (summer / Spring Festival / National Day) may extend to 30-40 working days.\n"
                "Validity: Typically issued as a multiple-entry visa valid for up to 1 year; each stay up to 3 months.\n"
                "Application Tips: Apply at least 1-2 months before travel; ensure all documents are in English or accompanied by certified translations."
            ),
        },
    ],
    "FR": [
        {
            "chunk_index": 0,
            "content": (
                "France Schengen Short-Stay Visa (Type C) Required Materials:\n"
                "1. Valid passport (issued within the last 10 years, valid for at least 3 months beyond the return date, with at least 2 blank pages)\n"
                "2. Schengen visa application form (filled and signed)\n"
                "3. Two recent white-background photos (35mm × 45mm, frontal)\n"
                "4. Travel medical insurance (covering Schengen area, minimum €30,000, valid for the entire stay)\n"
                "5. Round-trip flight reservation\n"
                "6. Hotel reservation or accommodation proof covering the entire stay\n"
                "7. Employment letter or enrollment certificate\n"
                "8. Recent bank statements (last 3 months)\n"
                "9. Personal income tax receipt or property deed (optional but strengthens application)"
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "France Schengen Visa Fees and Processing Time:\n"
                "Visa Fee: €80 EUR (adults), €40 EUR (children 6-12), free for children under 6.\n"
                "Processing Time: Standard 15 calendar days; may extend up to 45 days during peak season or if additional review is required.\n"
                "Validity: Short-stay visa (up to 90 days within 180 days); multiple-entry possible based on travel history.\n"
                "Application Tips: Schedule your appointment at the VFS Global visa center at least 4-6 weeks before travel; biometric data (fingerprints) is collected at the appointment."
            ),
        },
    ],
}


async def upsert_source(db, country_code: str) -> int:
    """Ensure a RagSource row exists for (country_code, lang); return its id."""
    existing = (await db.execute(
        select(RagSource).where(
            RagSource.country_code == country_code,
            RagSource.language == LANG,
        )
    )).scalar_one_or_none()
    if existing:
        return existing.id

    src = RagSource(
        name=f"Curated FAQ — {country_code} ({LANG})",
        country_code=country_code,
        language=LANG,
        url=None,
        content_type="curated",
        enabled=True,
        last_refresh_at=None,
        last_status="ok",
        last_error=None,
    )
    db.add(src)
    await db.flush()
    return src.id


async def upsert_chunks(db, source_id: int, country_code: str) -> int:
    """Upsert each curated chunk for this source. Returns count upserted."""
    items = CHUNKS.get(country_code, [])
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
        if existing:
            existing.content = c["content"]
            existing.embedding = json.dumps(emb)
            existing.embedding_dim = len(emb)
            existing.language = LANG
        else:
            db.add(RagChunk(
                source_id=source_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                embedding=json.dumps(emb),
                embedding_dim=len(emb),
                language=LANG,
            ))
        n += 1
    return n


async def main() -> None:
    async with AsyncSessionLocal() as db:
        total_sources = 0
        total_chunks = 0
        for cc in CHUNKS:
            sid = await upsert_source(db, cc)
            n = await upsert_chunks(db, sid, cc)
            total_sources += 1
            total_chunks += n
            print(f"  {cc}: source_id={sid}, {n} chunks upserted")
        await db.commit()
        print(f"Done. Sources={total_sources}, chunks upserted={total_chunks}, lang={LANG}")


if __name__ == "__main__":
    asyncio.run(main())