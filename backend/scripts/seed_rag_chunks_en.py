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
import hashlib
from datetime import date


# W47c METADATA PATCH
TOPIC_BY_INDEX = {0: "materials", 1: "fees", 2: "refusal"}

COUNTRY_META = {
    "US": ("b1_b2", "2025-09-30", "https://travel.state.gov/content/travel/en/us-visas.html"),
    "GB": ("standard_visitor", "2025-04-09", "https://www.gov.uk/standard-visitor"),
    "AU": ("subclass_600", "2025-07-01", "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600"),
    "FR": ("c_short_stay", "2024-06-11", "https://home-affairs.ec.europa.eu/policies/schengen-borders-visa-policy_en"),
}

LANG = "en"

# Per-country curated FAQ chunks — English variants of seed_rag_chunks.py
# content. Same 3-chunk structure (materials / fee+timing / rejection reasons)
# to keep parser parity between languages.
CHUNKS = {
    "US": [
        {
            "chunk_index": 0,
            "content": (
                "Visitor Visa (B-1 / B-2) — Required Documents (per travel.state.gov):\n"
                "1. Passport (must be valid for at least six months beyond your period of stay).\n"
                "2. DS-160 confirmation page (complete online and print before your interview).\n"
                "3. Application fee payment receipt (MRV $185, paid before interview).\n"
                "4. Photo (51mm × 51mm, white background, taken within 6 months).\n"
                "5. Proof of ties to home country (employment letter, business license, bank statements, or assets — to be requested if asked).\n"
                "Note: An invitation letter or Affidavit of Support is NOT required and is not a factor in the visa decision."
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Visitor Visa (B-1 / B-2) — Fees, Validity, Processing Time, and Stay (per travel.state.gov):\n"
                "Application (MRV) fee: $185 USD (non-refundable, paid before the interview for most nationalities).\n"
                "Issuance fee: An additional visa issuance fee may apply depending on your nationality (bilateral agreement).\n"
                "Validity: B-1/B-2 is generally issued as a 10-year multiple-entry visa for eligible nationals, but the validity is set by the consular officer and varies by country of nationality.\n"
                "Length of stay: A visa does not guarantee entry. U.S. Customs and Border Protection (CBP) officials at the port of entry decide how long you may stay — typically up to 6 months per visit. The period is shown on your admission stamp or Form I-94.\n"
                "Processing time: most applications are finalised within 5-15 business days from the interview; during peak seasons (summer, Chinese New Year) wait times can extend to 3-4 weeks. Fees and wait times vary by U.S. Embassy or Consulate. Check the specific embassy's website for current interview wait times."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Visitor Visa (B-1 / B-2) — Refusals, EVUS, and Overstay (per travel.state.gov):\n"
                "Refusal under Section 214(b) (Immigration and Nationality Act): applicants are presumed to have immigrant intent unless they can demonstrate strong ties to their home country (employment, family, property, etc.). The consular officer makes this determination. If refused, you may reapply if circumstances have changed.\n"
                "Misrepresentation or fraud may result in permanent visa ineligibility.\n"
                "Failure to depart on time results in being out of status. Under Section 222(g) of the INA, the visas of individuals who are out of status are automatically voided, and any multiple-entry visa voided for overstay is not valid for future entries.\n"
                "EVUS (Electronic Visa Update System) — required for citizens of the People's Republic of China holding a 10-year B-1, B-2, or B-1/B-2 visa. Enrollments are made at www.EVUS.gov; a $30 USD fee applies per enrollment (as of September 30, 2025). Update every two years, when you get a new passport, or when you get a new B-1, B-2, or B-1/B-2 visa — whichever happens first.\n"
                "Work is not permitted on a visitor visa. Do not make final travel plans or buy tickets until you have a valid visa."
            ),
        },
    ],
    "GB": [
        {
            "chunk_index": 0,
            "content": (
                "Standard Visitor visa (UK) — Required Documents (per GOV.UK):\n"
                "1. Passport (must be valid for the whole of your stay in the UK).\n"
                "2. Online application confirmation (apply online at GOV.UK before travel — no visa on arrival).\n"
                "3. Tuberculosis test certificate (required if you have lived in China for more than 6 months — must use a UK Home Office approved clinic).\n"
                "4. Proof of funds and travel plans (bank statements, accommodation booking, return or onward ticket).\n"
                "5. Supporting documents for the purpose of your visit (employment letter, business meeting invite, or tourist itinerary).\n"
                "Note: A visa does not guarantee entry — UK Border Force officers make the final decision at the border."
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Standard Visitor visa (UK) — Fees, Validity, and Processing Time (per GOV.UK):\n"
                "Application fee: £135 GBP for a Standard Visitor visa for up to 6 months (the standard short-term option). The earliest you can apply is 3 months before you travel. If transiting is your only reason for coming to the UK, you can apply for a Visitor in Transit visa instead for £74.50.\n"
                "Long-term Standard Visitor visa: 2-year, 5-year and 10-year options are also available, with higher fees. The 10-year long-term visa allows repeated visits of up to 6 months each.\n"
                "You must apply online at GOV.UK before you travel — there is no visa-on-arrival option for Chinese nationals.\n"
                "Tuberculosis (TB) test: applicants resident in China for more than 6 months must take a TB test at a clinic approved by the UK Home Office and submit the certificate with the application. Certificates from non-approved clinics are not accepted."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Standard Visitor visa (UK) — Eligibility and Refusals (per GOV.UK):\n"
                "To be eligible, you must show that: (1) you will leave the UK at the end of your visit, (2) you are able to support yourself and your dependants during the trip (or have funding from someone else), (3) you are able to pay for your return or onward journey, and (4) you will not live in the UK for extended periods through frequent or successive visits, or make the UK your main home.\n"
                "You need a passport or travel document valid for the whole of your stay.\n"
                "Common refusal reasons: insufficient evidence of funds or a clear source of income; unclear travel plans or no booked accommodation/return ticket; a previous immigration breach in the UK or another country; failing to attend a biometrics appointment. A previous refusal does not automatically mean a future refusal — reapply with stronger evidence.\n"
                "Applicants who are not Chinese nationals should check the GOV.UK 'Check if you need a UK visa' tool — many nationalities can visit visa-free for up to 6 months."
            ),
        },
    ],
    "AU": [
        {
            "chunk_index": 0,
            "content": (
                "Visitor visa (subclass 600) — Required Documents (per immi.homeaffairs.gov.au):\n"
                "1. Passport (must be valid for the duration of your intended stay).\n"
                "2. ImmiAccount application confirmation (apply online at the Department of Home Affairs website).\n"
                "3. Proof of funds (bank statements or evidence of income to support your stay in Australia).\n"
                "4. Travel itinerary and accommodation (flight bookings, hotel reservation, or host invitation).\n"
                "5. Ties to home country (employment letter, property, or family ties to show you will return).\n"
                "Note: Each stay is generally up to 3 months, recorded on the visa label."
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Visitor visa (subclass 600) — Fees, Validity, and Processing Time (per immi.homeaffairs.gov.au):\n"
                "Base application charge: AUD $190 for the most common tourist stream (further charges apply for subsequent applicants in the same application, and for longer-validity streams).\n"
                "Surcharges may apply: an additional charge may apply depending on the stream and the applicant's circumstances. Check the Department of Home Affairs 'Visa fees and charges' page for the current schedule.\n"
                "Processing time: most Visitor visa applications are finalised within a few weeks. Processing times vary by stream, country of application, and demand — check the global processing times tool on immi.homeaffairs.gov.au for the current estimate.\n"
                "Pay online by credit card when you submit through ImmiAccount. A second instalment may be requested before the visa is granted (e.g. for health examinations or biometrics if applicable).\n"
                "Validity: granted period is decided by the Department of Home Affairs — short-stay tourist streams are commonly issued for up to 12 months multiple entry, each stay up to 3 months. Longer streams (e.g. 3-year or 5-year frequent-traveller) are available for higher-risk, high-history applicants only."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Visitor visa (subclass 600) — Health, Character and Refusals (per immi.homeaffairs.gov.au):\n"
                "You must meet health and character requirements. Depending on your length of stay, country of citizenship, and intended activities, you may be asked to undergo a medical examination or a chest x-ray at a panel physician.\n"
                "You must be of good character. Any criminal record (including spent convictions in some cases) must be declared. A failure to declare can result in the visa being cancelled and a 3-year ban on future applications.\n"
                "Common refusal reasons: insufficient evidence of funds or employment ties to home country, prior overstay or visa cancellation in Australia or another country, false or misleading information in the application, and inability to demonstrate that the visit is genuinely temporary.\n"
                "If refused, you can apply again, or seek review at the Administrative Review Tribunal (ART). Each new application is assessed on its merits at the time of decision."
            ),
        },
    ],
    "FR": [
        {
            "chunk_index": 0,
            "content": (
                "Schengen short-stay visa (Type C) — Required Documents (per EU Visa Code):\n"
                "1. Passport (must be valid for at least 3 months beyond departure from the Schengen area, issued within the last 10 years, with at least 2 blank pages).\n"
                "2. Completed and signed visa application form (apply at the consulate of your main destination or first Schengen entry).\n"
                "3. Recent biometric photo (taken within the last 6 months).\n"
                "4. Travel medical insurance (minimum coverage €30,000, valid across the whole Schengen area for the entire stay).\n"
                "5. Proof of accommodation (hotel booking or host invitation letter).\n"
                "6. Round-trip or onward flight reservation (a booked itinerary showing entry into and exit from the Schengen area — actual tickets are not required).\n"
                "7. Proof of financial means (bank statements or sponsorship letter).\n"
                "8. Evidence of employment or studies (employer letter, payslips, or enrollment certificate).\n"
                "9. For minors, parental consent (if applicable).\n"
                "10. Biometrics (fingerprints collected at first application — stored in the Visa Information System (VIS) for 59 months, no new collection needed for subsequent applications at any member state during that period).\n"
                "Note: Apply to the consulate of the main destination (longest stay); if stays are equal, apply to the country of first entry."
            ),
        },
        {
            "chunk_index": 1,
            "content": (
                "Schengen short-stay visa (Type C) — Fees, Validity, and Processing Time (per EU Visa Code):\n"
                "Visa fee: €90 EUR for adults, €45 EUR for children aged 6 to under 12, free for children under 6 (per Commission Delegated Regulation (EU) 2024/1415, in force since 11 June 2024). Service fees charged by external providers such as VFS Global or TLScontact are additional.\n"
                "Validity: a Schengen short-stay visa allows a stay of up to 90 days within any 180-day period, and is typically valid across the whole Schengen area. The 180-day period is calculated from the date of first entry.\n"
                "Processing time: 15 calendar days from the application being admissible, extendable up to 45 days in individual cases. Visa-facilitation agreements with certain countries can shorten this.\n"
                "Legal basis: EU Visa Code (Reg. (EC) 810/2009, as amended by 2019/1155 and Commission Delegated Reg. (EU) 2024/1415)."
            ),
        },
        {
            "chunk_index": 2,
            "content": (
                "Schengen short-stay visa (Type C) — Refusals and Future Systems (per EU rules):\n"
                "If refused, the applicant receives a standard form stating the ground for refusal. Refusal grounds include: false or forged documents, failure to prove the purpose and conditions of the stay, insufficient means of subsistence, an entry ban in the Schengen Information System (SIS), or failure to demonstrate a genuine intention to return.\n"
                "Applicants have the right to appeal in the country that refused the visa. The appeal must be filed within the deadline set by national law of the refusing member state (often 15 to 30 days, varies by country).\n"
                "Coming changes: EES (Entry/Exit System) is being rolled out across the Schengen area; ETIAS (similar to US ESTA) is being introduced for visa-exempt travellers. These systems do not replace the visa requirement for non-exempt nationals, but they do affect border-crossing procedures.\n"
                "In January 2026, the European Commission adopted the first EU Visa Strategy, with a long-term direction toward more digitalised application processes and more efficient decision-making."
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