#!/usr/bin/env python3
"""Seed AU + GB destinations (idempotent).

The product pivoted (W31) to 4 lines: US / AU / GB / Schengen(FR-keyed RAG).
Migration 0002 only ever inserted US as enabled; AU/GB were never added to
this dev DB at all (alembic_version was stamped past 0002 without the
INSERT actually running against this SQLite file — schema is current,
seed data isn't). This script adds the two missing hero rows with the same
fee/valid_days/process_days figures already defined in migration 0009.

Run alongside scripts/seed_schengen_26.py to get the full 4-line catalog.
"""
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.destination import VisaDestination  # noqa: E402

# (country_code, name_i18n, fee_usd_cents, valid_days, process_days, display_order)
HERO_ROWS = [
    (
        "AU",
        {"zh-CN": "澳大利亚", "en": "Australia", "id": "Australia", "vi": "Úc"},
        14500, 365, 4, 2,
    ),
    (
        "GB",
        {"zh-CN": "英国", "en": "United Kingdom", "id": "Inggris", "vi": "Vương quốc Anh"},
        12500, 180, 3, 3,
    ),
]


async def main():
    async with AsyncSessionLocal() as db:
        for code, name_i18n, fee, valid, proc, order in HERO_ROWS:
            existing = (await db.execute(
                select(VisaDestination).where(VisaDestination.country_code == code)
            )).scalar_one_or_none()
            if existing:
                print(f"  exists: {code}")
                continue
            db.add(VisaDestination(
                country_code=code,
                country_name_i18n=json.dumps(name_i18n, ensure_ascii=False),
                visa_types=json.dumps(["tourism"], ensure_ascii=False),
                enabled=True,
                display_order=order,
                image_url=f"/images/{code.lower()}.jpg",
                visa_fee_usd=fee,
                valid_days=valid,
                process_days=proc,
            ))
            print(f"  added: {code}")
        await db.commit()

        rows = (await db.scalars(select(VisaDestination))).all()
        print(f"now {len(rows)} destinations")


if __name__ == "__main__":
    asyncio.run(main())
