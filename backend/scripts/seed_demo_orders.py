"""Add 2 demo orders (user 2 = created, user 3 = paid) so the demo accounts
have meaningful state to demonstrate.

Run AFTER rebuild_demo_users.py.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path("/Users/apple/Desktop/签证项目_副本/backend")
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.order import Order, OrderStatusHistory  # noqa: E402
from app.models.user import User  # noqa: E402


def _now() -> datetime:
    return datetime.utcnow()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        u2 = (await db.execute(select(User).where(User.username == "demo_user_2"))).scalar_one()
        u3 = (await db.execute(select(User).where(User.username == "demo_user_3"))).scalar_one()
        now = _now()

        # User 2: 1 created order (US, tourism), $199
        o1 = Order(
            uuid="11111111-1111-1111-1111-111111111111",
            order_no="DEMO-20260702-CREATED-001",
            user_id=u2.id,
            destination_id=1,  # US
            visa_type="tourism",
            status="created",
            total_amount=199.00,
            currency="USD",
            applicant_data=json.dumps(
                {
                    "full_name": "Demo Applicant 2",
                    "nationality": "CN",
                    "passport_no": "E22222222",
                    "birth_date": "1992-02-02",
                }
            ),
        )
        db.add(o1)
        await db.flush()
        db.add(
            OrderStatusHistory(
                order_id=o1.id,
                from_status=None,
                to_status="created",
                source="seed",
                note="rebuild_demo_users: created (awaiting payment)",
                created_at=now,
            )
        )

        # User 3: 1 paid + approved order (US, business), $299
        o2 = Order(
            uuid="22222222-2222-2222-2222-222222222222",
            order_no="DEMO-20260702-APPROVED-001",
            user_id=u3.id,
            destination_id=1,  # US
            visa_type="business",
            status="approved",
            total_amount=299.00,
            currency="USD",
            applicant_data=json.dumps(
                {
                    "full_name": "Demo Applicant 3",
                    "nationality": "CN",
                    "passport_no": "E33333333",
                    "birth_date": "1988-03-03",
                }
            ),
            submitted_at=now,
            reviewed_at=now,
            closed_at=now,
        )
        db.add(o2)
        await db.flush()
        for from_s, to_s in [
            (None, "created"),
            ("created", "paid"),
            ("paid", "submitted"),
            ("submitted", "approved"),
        ]:
            db.add(
                OrderStatusHistory(
                    order_id=o2.id,
                    from_status=from_s,
                    to_status=to_s,
                    source="seed" if from_s is None else "rpa",
                    note=f"rebuild_demo_users: {from_s or 'init'} → {to_s}",
                    created_at=now,
                )
            )

        await db.commit()
        print(f"created order for user 2 (id={u2.id}): {o1.order_no}  status=created")
        print(f"created order for user 3 (id={u3.id}): {o2.order_no}  status=approved")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
