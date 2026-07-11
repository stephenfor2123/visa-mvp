#!/usr/bin/env python3
"""Seed / update 26 Schengen countries (idempotent).

Replaces the single 'SCHENGEN' aggregate row with 26 individual country rows so
OrderNew can find the exact country the user picked (FR/DE/IT/...) instead of
falling back to the first enabled destination.

Writes proper 4-locale JSON into country_name_i18n (W58).
"""
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, select  # noqa: E402

from app.api.v2.destinations import _COUNTRY_NAME_EN_FALLBACK  # noqa: E402
from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.destination import VisaDestination  # noqa: E402

SCHENGEN_26 = [
    "AT", "BE", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS",
    "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "SK", "SI",
    "ES", "SE",
]


def _i18n_json(code: str) -> str:
    entry = _COUNTRY_NAME_EN_FALLBACK.get(code, {})
    if isinstance(entry, dict):
        name_map = dict(entry)
    else:
        name_map = {"en": str(entry or code)}
    name_map.setdefault("en", code)
    name_map.setdefault("zh-CN", name_map["en"])
    name_map.setdefault("id", name_map["en"])
    name_map.setdefault("vi", name_map["en"])
    return json.dumps(name_map, ensure_ascii=False)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(VisaDestination).where(VisaDestination.country_code == "SCHENGEN"))

        for idx, code in enumerate(SCHENGEN_26, start=5):
            existing = (
                await db.execute(
                    select(VisaDestination).where(VisaDestination.country_code == code)
                )
            ).scalar_one_or_none()
            i18n = _i18n_json(code)
            if existing:
                existing.country_name_i18n = i18n
                existing.enabled = True
                existing.display_order = idx
                existing.image_url = existing.image_url or f"/countries/{code.lower()}.jpg"
                print(f"  updated: {code}")
                continue

            db.add(
                VisaDestination(
                    country_code=code,
                    country_name_i18n=i18n,
                    visa_types=json.dumps(["tourism", "student", "work"], ensure_ascii=False),
                    enabled=True,
                    display_order=idx,
                    image_url=f"/countries/{code.lower()}.jpg",
                )
            )
            print(f"  added: {code}")

        await db.commit()
        n = len((await db.scalars(select(VisaDestination))).all())
        print(f"now {n} destinations")


if __name__ == "__main__":
    asyncio.run(main())
