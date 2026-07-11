"""Seed 6 个内置 admin 角色。

启动时由 app.main 在 create_all 后调用,确保每个角色的 permissions
与 PERMISSIONS 单一源对齐。已存在的角色 code 跳过(保留手工调整)。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal as async_session_maker
from app.core.permissions import ROLE_PERMISSIONS
from app.models.admin_role import AdminRole

_log = logging.getLogger(__name__)


async def seed_admin_roles(db: AsyncSession) -> dict[str, int]:
    """确保 6 个内置角色存在并 permissions 对齐。

    Returns:
        dict[code, role_id]
    """
    result: dict[str, int] = {}
    for code, cfg in ROLE_PERMISSIONS.items():
        existing = (
            await db.execute(select(AdminRole).where(AdminRole.code == code))
        ).scalar_one_or_none()
        if existing is None:
            role = AdminRole(
                name=cfg["name"],
                code=code,
                permissions=cfg["permissions"],
                description=cfg["description"],
                is_active=True,
            )
            db.add(role)
            _log.info("seed_admin_role: created %s", code)
        else:
            # 已存在 → 对齐 permissions/name/description(覆盖,避免 perm 注册表漂移)
            existing.name = cfg["name"]
            existing.description = cfg["description"]
            existing.permissions = cfg["permissions"]
            existing.is_active = True
            _log.debug("seed_admin_role: aligned %s", code)
            result[code] = existing.id
            continue
        # 新建走这里 flush 拿到 id
        await db.flush()
        result[code] = role.id
    await db.commit()
    return result


async def run_seed() -> None:
    """入口:可独立运行 `PYTHONPATH=. python -m app.core.seed_admin_roles`"""
    async with async_session_maker() as db:
        ids = await seed_admin_roles(db)
        print(f"Seeded {len(ids)} roles: {ids}")


if __name__ == "__main__":
    asyncio.run(run_seed())