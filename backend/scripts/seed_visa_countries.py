#!/usr/bin/env python3
"""Seed visa_countries for admin config panel (idempotent).

Only product fileable destinations: US / AU / GB / DE / FR.
Legacy ID/VN/PH (and other non-product) rows are deleted — we do not file
those visas. Indonesia/Vietnam remain customer markets (passport holders)
elsewhere in the product, not admin country-config destinations.
"""
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.core.product_scope import (  # noqa: E402
    NON_PRODUCT_DESTINATION_CODES,
    PRODUCT_DESTINATION_CODES,
    normalize_destination_code,
)
from app.models.visa_countries import VisaCountry  # noqa: E402

# (country_code, zh, en, emoji, enabled, display_order, visa_types)
PRODUCT_ROWS = [
    ("US", "美国", "United States", "🇺🇸", True, 1, ["tourism", "student"]),
    ("AU", "澳大利亚", "Australia", "🇦🇺", True, 2, ["tourism"]),
    ("GB", "英国", "United Kingdom", "🇬🇧", True, 3, ["tourism"]),
    ("DE", "德国(申根)", "Germany (Schengen)", "🇩🇪", True, 4, ["tourism"]),
    ("FR", "法国(申根)", "France (Schengen)", "🇫🇷", True, 5, ["tourism"]),
]


async def upsert_country(
    db,
    *,
    code,
    zh,
    en,
    emoji,
    enabled,
    display_order,
    visa_types,
):
    row = (
        await db.execute(select(VisaCountry).where(VisaCountry.country_code == code))
    ).scalar_one_or_none()
    types_json = json.dumps(visa_types, ensure_ascii=False)
    if row:
        row.country_name_zh = zh
        row.country_name_en = en
        row.flag_emoji = emoji
        row.enabled = enabled
        row.display_order = display_order
        row.visa_types = types_json
        return "updated"

    db.add(
        VisaCountry(
            country_code=code,
            country_name_zh=zh,
            country_name_en=en,
            flag_emoji=emoji,
            enabled=enabled,
            display_order=display_order,
            visa_types=types_json,
        )
    )
    return "added"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # Purge non-product destination rows from admin config
        result = await db.execute(
            delete(VisaCountry).where(
                VisaCountry.country_code.in_(sorted(NON_PRODUCT_DESTINATION_CODES))
            )
        )
        print(f"  purged non-product visa_countries: {result.rowcount}")

        product_norm = {normalize_destination_code(c) for c in PRODUCT_DESTINATION_CODES}
        for code, zh, en, emoji, enabled, order, types in PRODUCT_ROWS:
            if normalize_destination_code(code) not in product_norm:
                continue
            action = await upsert_country(
                db,
                code=code,
                zh=zh,
                en=en,
                emoji=emoji,
                enabled=enabled,
                display_order=order,
                visa_types=types,
            )
            print(f"  {action}: {code}")

        await db.commit()
        rows = (await db.scalars(select(VisaCountry))).all()
        codes = sorted(r.country_code for r in rows)
        print(f"now {len(rows)} visa_countries rows: {codes}")


if __name__ == "__main__":
    asyncio.run(main())
