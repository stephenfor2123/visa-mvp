"""Seed RAG sources for the official-info RAG demo.

Idempotent — re-running only inserts missing sources (matched by name+country).
"""
from __future__ import annotations

import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.rag import RagSource

SOURCES = [
    {
        "name": "印尼移民局官网首页",
        "country_code": "ID",
        "url": "https://www.imigrasi.go.id",
        "content_type": "web",
        "enabled": True,
    },
    {
        "name": "印尼签证申请要求 (curated FAQ)",
        "country_code": "ID",
        "url": None,
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "越南签证指南 (curated FAQ)",
        "country_code": "VN",
        "url": None,
        "content_type": "curated",
        "enabled": True,
    },
    # W25: add main 6 destinations (US/FR/JP/KR/SG/GB) for diagnose policy_refs
    {
        "name": "美国 B1/B2 旅游商务签证 (curated FAQ)",
        "country_code": "US",
        "url": "https://travel.state.gov",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "法国 Schengen 短期签证 (curated FAQ)",
        "country_code": "FR",
        "url": "https://france-visas.gouv.fr",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "日本旅游签证 (curated FAQ)",
        "country_code": "JP",
        "url": "https://www.mofa.go.jp",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "韩国旅游签证 (curated FAQ)",
        "country_code": "KR",
        "url": "https://overseas.mofa.go.kr",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "新加坡旅游签证 (curated FAQ)",
        "country_code": "SG",
        "url": "https://www.ica.gov.sg",
        "content_type": "curated",
        "enabled": True,
    },
    {
        "name": "英国旅游签证 (curated FAQ)",
        "country_code": "GB",
        "url": "https://www.gov.uk/standard-visitor",
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
