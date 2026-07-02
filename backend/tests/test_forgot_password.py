"""忘记密码（reset-password）回归测试

覆盖内容:
  1. 通过邮箱重置密码 → 成功
  2. 通过用户名重置密码 → 成功
  3. 重置后用新密码可登录，旧密码失效
  4. 账号不存在 → USER_NOT_FOUND (3001)
  5. 新密码强度不足 → 错误
  6. 新密码过短/过长 → 错误
  7. 缺少字段 → 错误
  8. 重置后写入 audit log
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.audit_log import AuditLog


# ------------------------------------------------------------------ #
# helpers                                                              #
# ------------------------------------------------------------------ #
async def _register(client, username: str, email: str, password: str = "Pass1234") -> str:
    r = await client.post(
        "/api/v2/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["access_token"]


async def _login(client, account: str, password: str) -> dict:
    return await client.post(
        "/api/v2/auth/login",
        json={"account": account, "password": password},
    )


async def _reset(client, account: str, new_password: str) -> dict:
    return await client.post(
        "/api/v2/auth/reset-password",
        json={"account": account, "new_password": new_password},
    )


# ------------------------------------------------------------------ #
# 1. 通过邮箱重置密码                                                  #
# ------------------------------------------------------------------ #
class TestResetByEmail:
    async def test_reset_by_email_returns_200(self, client):
        await _register(client, "rset_u1", "rset1@htex.test")
        r = await _reset(client, "rset1@htex.test", "NewPass99")
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "1000"

    async def test_reset_by_email_new_password_works(self, client):
        await _register(client, "rset_u2", "rset2@htex.test", "OldPass1")
        await _reset(client, "rset2@htex.test", "NewPass99")

        r = await _login(client, "rset2@htex.test", "NewPass99")
        assert r.status_code == 200, "新密码应可登录"

    async def test_reset_by_email_old_password_rejected(self, client):
        await _register(client, "rset_u3", "rset3@htex.test", "OldPass1")
        await _reset(client, "rset3@htex.test", "NewPass99")

        r = await _login(client, "rset3@htex.test", "OldPass1")
        assert r.status_code == 401, "旧密码应被拒绝 (401)"


# ------------------------------------------------------------------ #
# 2. 通过用户名重置密码                                                #
# ------------------------------------------------------------------ #
class TestResetByUsername:
    async def test_reset_by_username_returns_200(self, client):
        await _register(client, "rset_un1", "rset_un1@htex.test")
        r = await _reset(client, "rset_un1", "NewPass99")
        assert r.status_code == 200, r.text

    async def test_reset_by_username_new_password_works(self, client):
        await _register(client, "rset_un2", "rset_un2@htex.test", "OldPass1")
        await _reset(client, "rset_un2", "NewPass88")

        r = await _login(client, "rset_un2", "NewPass88")
        assert r.status_code == 200, "通过用户名重置后可用新密码登录"

    async def test_reset_by_username_email_login_also_works(self, client):
        """重置后用邮箱也能用新密码登录"""
        await _register(client, "rset_un3", "rset_un3@htex.test", "OldPass1")
        await _reset(client, "rset_un3", "NewPass88")

        r = await _login(client, "rset_un3@htex.test", "NewPass88")
        assert r.status_code == 200, "邮箱 + 新密码也应能登录"


# ------------------------------------------------------------------ #
# 3. 连续重置                                                          #
# ------------------------------------------------------------------ #
class TestResetTwice:
    async def test_can_reset_password_twice(self, client):
        await _register(client, "rset_2x", "rset2x@htex.test", "OldPass1")

        await _reset(client, "rset_2x", "MidPass22")
        r = await _login(client, "rset_2x", "MidPass22")
        assert r.status_code == 200

        await _reset(client, "rset_2x", "FinalPass3")
        r = await _login(client, "rset_2x", "FinalPass3")
        assert r.status_code == 200, "第二次重置后应可用最新密码登录"

        r = await _login(client, "rset_2x", "MidPass22")
        assert r.status_code == 401, "中间密码应失效"


# ------------------------------------------------------------------ #
# 4. 账号不存在                                                        #
# ------------------------------------------------------------------ #
class TestResetUnknownAccount:
    async def test_unknown_email_returns_error(self, client):
        r = await _reset(client, "nobody@htex.test", "NewPass99")
        assert r.status_code == 404, r.text
        assert r.json()["code"] == "3001"

    async def test_unknown_username_returns_error(self, client):
        r = await _reset(client, "ghost_user_xyz", "NewPass99")
        assert r.status_code == 404, r.text
        assert r.json()["code"] == "3001"

    async def test_empty_account_returns_error(self, client):
        r = await _reset(client, "", "NewPass99")
        assert r.status_code == 400, r.text


# ------------------------------------------------------------------ #
# 5. 新密码强度校验                                                    #
# ------------------------------------------------------------------ #
class TestResetPasswordStrength:
    async def test_too_short_password_rejected(self, client):
        await _register(client, "rset_str1", "rset_str1@htex.test")
        r = await _reset(client, "rset_str1@htex.test", "Ab1")
        assert r.status_code == 400, "过短密码应被拒绝"

    async def test_no_digit_password_rejected(self, client):
        await _register(client, "rset_str2", "rset_str2@htex.test")
        r = await _reset(client, "rset_str2@htex.test", "NoDigitPwd")
        assert r.status_code in (400, 422), "无数字密码应被拒绝"

    async def test_no_letter_password_rejected(self, client):
        await _register(client, "rset_str3", "rset_str3@htex.test")
        r = await _reset(client, "rset_str3@htex.test", "12345678")
        assert r.status_code in (400, 422), "无字母密码应被拒绝"

    async def test_too_long_password_rejected(self, client):
        await _register(client, "rset_str4", "rset_str4@htex.test")
        r = await _reset(client, "rset_str4@htex.test", "A1" + "x" * 40)
        assert r.status_code == 400, "超长密码应被拒绝"

    async def test_valid_strong_password_accepted(self, client):
        await _register(client, "rset_str5", "rset_str5@htex.test")
        r = await _reset(client, "rset_str5@htex.test", "Str0ng!Pass#99")
        assert r.status_code == 200, r.text


# ------------------------------------------------------------------ #
# 6. 缺少必填字段                                                      #
# ------------------------------------------------------------------ #
class TestResetMissingFields:
    async def test_missing_new_password_rejected(self, client):
        r = await client.post(
            "/api/v2/auth/reset-password",
            json={"account": "someone@htex.test"},
        )
        assert r.status_code == 400

    async def test_missing_account_rejected(self, client):
        r = await client.post(
            "/api/v2/auth/reset-password",
            json={"new_password": "NewPass99"},
        )
        assert r.status_code == 400

    async def test_empty_body_rejected(self, client):
        r = await client.post("/api/v2/auth/reset-password", json={})
        assert r.status_code == 400


# ------------------------------------------------------------------ #
# 7. Audit log 写入                                                    #
# ------------------------------------------------------------------ #
class TestResetAuditLog:
    async def test_reset_writes_audit_log(self, client):
        await _register(client, "rset_aud1", "rset_aud1@htex.test")
        await _reset(client, "rset_aud1@htex.test", "NewPass99")

        async with AsyncSessionLocal() as s:
            log = await s.scalar(
                select(AuditLog)
                .where(AuditLog.action == "user.reset_password")
                .order_by(AuditLog.id.desc())
            )
        assert log is not None, "重置密码应写入 audit log"
        assert log.action == "user.reset_password"

    async def test_failed_reset_does_not_write_audit(self, client):
        """账号不存在时不应写入 audit log"""
        async with AsyncSessionLocal() as s:
            before = await s.scalar(
                select(AuditLog)
                .where(AuditLog.action == "user.reset_password")
                .order_by(AuditLog.id.desc())
            )
        before_id = before.id if before else 0

        await _reset(client, "nonexistent_xyz@htex.test", "NewPass99")

        async with AsyncSessionLocal() as s:
            after = await s.scalar(
                select(AuditLog)
                .where(AuditLog.action == "user.reset_password")
                .order_by(AuditLog.id.desc())
            )
        after_id = after.id if after else 0
        assert after_id == before_id, "失败的重置不应写 audit log"
