"""Rebuild 3 demo users for Htex dev DB. Bypasses seed_demo_data.py (which
still uses phone columns dropped in W26). Uses real AuthService.register so
the rows match what production registration would write.
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path("/Users/apple/Desktop/签证项目_副本/backend")
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.material import Material  # noqa: E402
from app.models.order import Order, OrderStatusHistory  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402

DEMO_PASSWORD = "Htex@2026"  # 8 chars, satisfies PASSWORD_MIN_LENGTH=8

USERS = [
    {
        "username": "demo_user_1",
        "email": "demo1@htex.local",
        "nickname": "Demo User 1 (new)",
        "role": "empty — fresh signup, no orders",
    },
    {
        "username": "demo_user_2",
        "email": "demo2@htex.local",
        "nickname": "Demo User 2 (created order)",
        "role": "1 created order, awaiting payment",
    },
    {
        "username": "demo_user_3",
        "email": "demo3@htex.local",
        "nickname": "Demo User 3 (approved)",
        "role": "1 approved order, end-to-end complete",
    },
]


async def main() -> int:
    async with AsyncSessionLocal() as db:
        # Clean slate (in case previous run half-completed).
        await db.execute(delete(OrderStatusHistory))
        await db.execute(delete(Order))
        await db.execute(delete(Material))
        await db.execute(delete(User))
        await db.commit()

        svc = AuthService(db)
        created: list[dict] = []
        for spec in USERS:
            result = await svc.register(
                username=spec["username"],
                email=spec["email"],
                password=DEMO_PASSWORD,
                nickname=spec["nickname"],
                language_pref="zh-CN",
                info={"ip": "127.0.0.1", "user_agent": "rebuild_demo_users/1.0"},
            )
            u = result["user"]
            created.append(
                {
                    "id": u["id"],
                    "uuid": u.get("uuid"),
                    "username": u["username"],
                    "email": u["email"],
                    "nickname": u.get("nickname"),
                }
            )

        await db.commit()

    print("=== demo users rebuilt ===")
    for u in created:
        print(f"  id={u['id']:>3}  username={u['username']:<14}  email={u['email']:<22}  nickname={u['nickname']}")
    print()
    print(f"password (all 3): {DEMO_PASSWORD}  ({len(DEMO_PASSWORD)} chars, meets PASSWORD_MIN_LENGTH=8)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
