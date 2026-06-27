"""Seed RAG sources for the official-info RAG demo.

Idempotent — re-running only inserts missing sources (matched by name+country).

W31: refocus on user's 4 product lines: 欧洲(GB) / 申根(FR 代理) / 美国(US) / 澳洲(AU).
Remove: ID/VN/JP/KR/SG + ID_web (not in product scope).
"""
from __future__ import annotations

import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.rag import RagSource

SOURCES = [
    # 4 product lines (country_code is the canonical code; frontend labels differ)
    {
        "name": "英国 Standard Visitor 签证 (curated FAQ)",
        "country_code": "GB",
        "url": "https://www.gov.uk/standard-visitor",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "申根 (Schengen) 短期签证 (curated FAQ)",
        "country_code": "FR",
        "url": "https://france-visas.gouv.fr",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "美国 B1/B2 旅游商务签证 (curated FAQ)",
        "country_code": "US",
        "url": "https://travel.state.gov",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "澳大利亚旅游签证 (curated FAQ)",
        "country_code": "AU",
        "url": "https://immi.homeaffairs.gov.au",
        "content_type": "curated",
        "enabled": True,
    },
]


async def main():
    async with AsyncSessionLocal() as db:
        for src in SOURCES:
            stmt = select(RagSource).where(
                RagSource.name == src["name"],
                RagSource.country_code == src["country_code"],
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing:
                print(f"  exists: {src['name']}")
                continue
            db.add(RagSource(**src))
            print(f"  added: {src['name']}")
        await db.commit()
    print("seed done")


if __name__ == "__main__":
    asyncio.run(main())
