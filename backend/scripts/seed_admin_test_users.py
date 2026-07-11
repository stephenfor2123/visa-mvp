"""e2e 测试用的 admin 账号 seeder。

为 admin-permissions.spec.js 创建:
  - reviewer1 / Test1234!  (reviewer 角色)
  - finance1  / Test1234!  (finance 角色)

idempotent — 重复运行不会创建重复账号。
"""
from __future__ import annotations

import asyncio

import bcrypt
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.permissions import ROLE_PERMISSIONS
from app.core.seed_admin_roles import seed_admin_roles
from app.models.admin_role import AdminRole
from app.models.admin_user import AdminUser


TEST_USERS = [
    {"username": "reviewer1", "password": "Test1234!", "role_code": "reviewer"},
    {"username": "finance1",  "password": "Test1234!", "role_code": "finance"},
    {"username": "ops1",      "password": "Test1234!", "role_code": "ops_manager"},
]


async def main():
    async with AsyncSessionLocal() as db:
        # 1) 确保 6 个内置角色在
        await seed_admin_roles(db)
        await db.commit()

        # 2) 创建/更新测试账号
        for spec in TEST_USERS:
            existing = (
                await db.execute(
                    select(AdminUser).where(AdminUser.username == spec["username"])
                )
            ).scalar_one_or_none()
            role = (
                await db.execute(
                    select(AdminRole).where(AdminRole.code == spec["role_code"])
                )
            ).scalar_one_or_none()
            if not role:
                print(f"  ! role {spec['role_code']} not found, skip {spec['username']}")
                continue
            if existing:
                existing.password_hash = bcrypt.hashpw(
                    spec["password"].encode(), bcrypt.gensalt()
                ).decode()
                existing.role_id = role.id
                existing.is_active = True
                print(f"  updated {spec['username']} -> {spec['role_code']}")
            else:
                u = AdminUser(
                    username=spec["username"],
                    password_hash=bcrypt.hashpw(
                        spec["password"].encode(), bcrypt.gensalt()
                    ).decode(),
                    role_id=role.id,
                    is_active=True,
                )
                db.add(u)
                print(f"  created {spec['username']} -> {spec['role_code']}")
        await db.commit()
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())