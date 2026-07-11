#!/usr/bin/env python3
"""Seed visa_countries for admin config panel (idempotent).

Migration 0007 inserts ID/VN/PH only; dev DBs stamped past migrations often
have zero rows. This script upserts the V2 product-line countries:
US / AU / GB + 26 Schengen members.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.api.v2.destinations import _COUNTRY_NAME_EN_FALLBACK  # noqa: E402
from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.visa_countries import VisaCountry  # noqa: E402

# (country_code, enabled, display_order, fee_usd, processing_days)
PRODUCT_ROWS = [
    ("US", True, 1, 185.0, 5),
    ("AU", True, 2, 145.0, 4),
    ("GB", True, 3, 125.0, 3),
]
SCHENGEN_CODES = [
    "AT", "BE", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS",
    "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "SK", "SI",
    "ES", "SE",
]


def _names(code: str):
    entry = _COUNTRY_NAME_EN_FALLBACK.get(code, {})
    if isinstance(entry, dict):
        zh = entry.get("zh-CN") or code
        en = entry.get("en") or code
    else:
        zh = en = str(entry or code)
    return zh, en


async def upsert_country(db, *, code, enabled, display_order, fee_usd=None, processing_days=None):
    zh, en = _names(code)
    row = (
        await db.execute(select(VisaCountry).where(VisaCountry.country_code == code))
    ).scalar_one_or_none()
    visa_types = json.dumps(["tourism", "student"], ensure_ascii=False)
    if row:
        row.country_name_zh = zh
        row.country_name_en = en
        row.enabled = enabled
        row.display_order = display_order
        row.visa_types = visa_types
        if fee_usd is not None:
            row.fee_usd = fee_usd
        if processing_days is not None:
            row.processing_days = processing_days
        return "updated"

    db.add(
        VisaCountry(
            country_code=code,
            country_name_zh=zh,
            country_name_en=en,
            enabled=enabled,
            display_order=display_order,
            visa_types=visa_types,
            fee_usd=fee_usd,
            processing_days=processing_days,
        )
    )
    return "added"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for code, enabled, order, fee, proc in PRODUCT_ROWS:
            action = await upsert_country(
                db, code=code, enabled=enabled, display_order=order,
                fee_usd=fee, processing_days=proc,
            )
            print(f"  {action}: {code}")

        for idx, code in enumerate(SCHENGEN_CODES, start=10):
            action = await upsert_country(
                db, code=code, enabled=True, display_order=idx,
            )
            print(f"  {action}: {code}")

        await db.commit()
        n = len((await db.scalars(select(VisaCountry))).all())
        print(f"now {n} visa_countries rows")


if __name__ == "__main__":
    asyncio.run(main())
