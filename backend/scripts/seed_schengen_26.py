#!/usr/bin/env python3
"""Seed 26 Schengen countries + remove old SCHENGEN aggregate entry.

Replaces the single 'SCHENGEN' row with 26 individual country rows so that
OrderNew can find the exact country the user picked (FR/DE/IT/...) instead
of falling back to the first enabled destination.
"""
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, delete  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.destination import VisaDestination  # noqa: E402


SCHENGEN_26 = [
    ('AT', 'Austria'),       ('BE', 'Belgium'),       ('HR', 'Croatia'),
    ('CZ', 'Czechia'),       ('DK', 'Denmark'),       ('EE', 'Estonia'),
    ('FI', 'Finland'),       ('FR', 'France'),        ('DE', 'Germany'),
    ('GR', 'Greece'),        ('HU', 'Hungary'),       ('IS', 'Iceland'),
    ('IT', 'Italy'),         ('LV', 'Latvia'),        ('LI', 'Liechtenstein'),
    ('LT', 'Lithuania'),     ('LU', 'Luxembourg'),    ('MT', 'Malta'),
    ('NL', 'Netherlands'),   ('NO', 'Norway'),        ('PL', 'Poland'),
    ('PT', 'Portugal'),      ('SK', 'Slovakia'),      ('SI', 'Slovenia'),
    ('ES', 'Spain'),         ('SE', 'Sweden'),
]


async def main():
    async with AsyncSessionLocal() as db:
        # Remove the old 'SCHENGEN' aggregate row (if any)
        await db.execute(delete(VisaDestination).where(VisaDestination.country_code == 'SCHENGEN'))

        for idx, (code, name) in enumerate(SCHENGEN_26, start=5):
            d = VisaDestination(
                country_code=code,
                country_name_i18n=name,
                visa_types=json.dumps(['tourism', 'student', 'work'], ensure_ascii=False),
                enabled=True,
                display_order=idx,
                image_url=f'/countries/{code.lower()}.jpg',
            )
            db.add(d)
        await db.commit()

        n = (await db.scalars(select(VisaDestination))).all()
        print(f'now {len(n)} destinations')


if __name__ == "__main__":
    asyncio.run(main())
