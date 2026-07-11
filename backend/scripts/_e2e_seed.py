"""One-shot seed: create US destination + a demo order with full applicant_data."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import AsyncSessionLocal
from app.models.destination import VisaDestination
from app.models.order import Order
from app.models.applicant import Applicant  # noqa
from app.models.user import User  # noqa
from app.models.material import Material  # noqa
from sqlalchemy import select


async def seed():
    async with AsyncSessionLocal() as s:
        # 1. Ensure US destination exists
        existing = await s.scalar(
            select(VisaDestination).where(VisaDestination.country_code == "US")
        )
        if existing is None:
            dest = VisaDestination(
                country_code="US",
                country_name_i18n=json.dumps(
                    {"en": "United States", "zh-CN": "美国", "vi": "Hoa Kỳ", "id": "Amerika Serikat"},
                    ensure_ascii=False,
                ),
                visa_types=json.dumps(["tourism"]),
                enabled=True,
                display_order=10,
            )
            s.add(dest)
            await s.commit()
            await s.refresh(dest)
            print(f"Seeded destination id={dest.id}")
        else:
            print(f"Destination already exists id={existing.id}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed()))