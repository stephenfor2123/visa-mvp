#!/usr/bin/env python3
"""W26 migration: 给 users 表加 email/username 列 + 给老 user 生成占位符。

两步:
  1. ALTER TABLE users ADD COLUMN email VARCHAR(120) / username VARCHAR(32)
     (sqlite 不支持 IF NOT EXISTS,容错 catch)
  2. 把 email IS NULL 或 username IS NULL 的 user 补上占位符

W26 product change: account identifier 从 phone 改为 email/username。
老 user 的占位符:
  email    = `{phone_country}{phone}@htex.local`  (e.g. +8613800000000@htex.local)
  username = `user_{phone_last4}_{user.id}`

老用户能继续登录,登录后管理员可提示他们改 email + username。

幂等:重跑不会重复设置。
"""
import asyncio
import sys
from pathlib import Path

# 把 backend/ 加到 path
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select, text  # noqa: E402

from app.core.db import AsyncSessionLocal, engine  # noqa: E402
from app.models.user import User  # noqa: E402


async def add_columns():
    """先给 users 表加 email + username 列(idempotent: 失败说明已存在)。"""
    async with engine.begin() as conn:
        for sql in [
            "ALTER TABLE users ADD COLUMN email VARCHAR(120)",
            "ALTER TABLE users ADD COLUMN username VARCHAR(32)",
        ]:
            try:
                await conn.execute(text(sql))
                print(f"  [alter] {sql}")
            except Exception as e:
                # sqlite: 'duplicate column name' / 其他 db: 'column already exists'
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"  [skip] column exists, ignoring: {sql}")
                else:
                    raise
        # 加 unique index
        try:
            await conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
            print("  [index] ix_users_email created")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("  [skip] ix_users_email exists")
            else:
                raise
        try:
            await conn.execute(text("CREATE UNIQUE INDEX ix_users_username ON users (username)"))
            print("  [index] ix_users_username created")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("  [skip] ix_users_username exists")
            else:
                raise


async def backfill():
    async with AsyncSessionLocal() as db:
        users = (await db.scalars(
            select(User).where((User.email.is_(None)) | (User.username.is_(None)))
        )).all()

        if not users:
            print("[backfill_w26] 没有需要补全的 user,跳过。")
            return 0

        updated = 0
        for u in users:
            phone = (u.phone or "").strip()
            phone_country = (u.phone_country or "+86").strip()
            if not u.email:
                u.email = f"{phone_country}{phone}@htex.local"
            if not u.username:
                suffix = phone[-4:] if phone else f"u{u.id}"
                u.username = f"user_{suffix}_{u.id}"
            updated += 1
            print(f"  [user.id={u.id}] email={u.email} username={u.username}")

        await db.commit()
        print(f"[backfill_w26] 已补全 {updated} 个 user 的 email/username。")
        return updated


async def main():
    print("[migration_w26] step 1: ALTER TABLE")
    await add_columns()
    print("[migration_w26] step 2: backfill placeholder email/username")
    await backfill()
    print("[migration_w26] done.")


if __name__ == "__main__":
    asyncio.run(main())
