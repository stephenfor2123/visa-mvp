"""忘记密码（email token 流程）回归测试"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.audit_log import AuditLog


OUTBOX = Path(__file__).resolve().parents[2] / "logs" / "email_outbox"


async def _register(client, username: str, email: str, password: str = "Pass1234") -> str:
    r = await client.post(
        "/api/v2/auth/register",
        json={"username": username, "email": email, "password": password, "email_code": "123456"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["access_token"]


async def _login(client, account: str, password: str) -> dict:
    return await client.post(
        "/api/v2/auth/login",
        json={"account": account, "password": password},
    )


async def _request_reset(client, account: str) -> dict:
    return await client.post(
        "/api/v2/auth/password-reset-request",
        json={"account": account},
    )


def _latest_reset_token_for(email_prefix: str) -> str:
    """Parse token from the newest password-reset outbox email for this user."""
    files = sorted(OUTBOX.glob(f"*_password_reset_{email_prefix}*.eml"), reverse=True)
    assert files, f"no password reset email in outbox for {email_prefix}"
    content = files[0].read_text(encoding="utf-8")
    m = re.search(r"token=([A-Za-z0-9._-]+)", content)
    assert m, "token not found in reset email"
    return m.group(1)


async def _reset_with_token(client, token: str, new_password: str) -> dict:
    return await client.post(
        "/api/v2/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )


class TestPasswordResetRequest:
    async def test_request_always_returns_200(self, client):
        await _register(client, "rset_u1", "rset1@htex.test")
        r = await _request_reset(client, "rset1@htex.test")
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "1000"

    async def test_unknown_account_still_returns_200(self, client):
        r = await _request_reset(client, "nobody@htex.test")
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "1000"


class TestResetByEmail:
    async def test_reset_by_email_new_password_works(self, client):
        await _register(client, "rset_u2", "rset2@htex.test", "OldPass1")
        await _request_reset(client, "rset2@htex.test")
        token = _latest_reset_token_for("rset2")
        r = await _reset_with_token(client, token, "NewPass99")
        assert r.status_code == 200, r.text

        r = await _login(client, "rset2@htex.test", "NewPass99")
        assert r.status_code == 200, "新密码应可登录"

    async def test_reset_by_email_old_password_rejected(self, client):
        await _register(client, "rset_u3", "rset3@htex.test", "OldPass1")
        await _request_reset(client, "rset3@htex.test")
        token = _latest_reset_token_for("rset3")
        await _reset_with_token(client, token, "NewPass99")

        r = await _login(client, "rset3@htex.test", "OldPass1")
        assert r.status_code == 401, "旧密码应被拒绝 (401)"


class TestResetByUsername:
    async def test_reset_by_username_sends_to_registered_email(self, client):
        await _register(client, "rset_un1", "rset_un1@htex.test", "OldPass1")
        await _request_reset(client, "rset_un1")
        token = _latest_reset_token_for("rset_un1")
        r = await _reset_with_token(client, token, "NewPass88")
        assert r.status_code == 200, r.text

        r = await _login(client, "rset_un1", "NewPass88")
        assert r.status_code == 200


class TestResetPasswordStrength:
    async def test_too_short_password_rejected(self, client):
        await _register(client, "rset_str1", "rset_str1@htex.test")
        await _request_reset(client, "rset_str1@htex.test")
        token = _latest_reset_token_for("rset_str1")
        r = await _reset_with_token(client, token, "Ab1")
        assert r.status_code == 400, "过短密码应被拒绝"

    async def test_valid_strong_password_accepted(self, client):
        await _register(client, "rset_str5", "rset_str5@htex.test")
        await _request_reset(client, "rset_str5@htex.test")
        token = _latest_reset_token_for("rset_str5")
        r = await _reset_with_token(client, token, "Str0ng!Pass#99")
        assert r.status_code == 200, r.text


class TestResetAuditLog:
    async def test_reset_writes_audit_log(self, client):
        await _register(client, "rset_aud1", "rset_aud1@htex.test")
        await _request_reset(client, "rset_aud1@htex.test")
        token = _latest_reset_token_for("rset_aud1")
        await _reset_with_token(client, token, "NewPass99")

        async with AsyncSessionLocal() as s:
            log = await s.scalar(
                select(AuditLog)
                .where(AuditLog.action == "user.reset_password")
                .order_by(AuditLog.id.desc())
            )
        assert log is not None, "重置密码应写入 audit log"
        assert log.action == "user.reset_password"
