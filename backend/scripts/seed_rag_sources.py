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
