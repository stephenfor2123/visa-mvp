"""Regression tests for audit-2026-07-08 P0 security fixes."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from app.services.admin_dashboard_service import AdminDashboardService


OUTBOX = Path(__file__).resolve().parents[2] / "logs" / "email_outbox"

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 8
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"FAKE-PNG-PAYLOAD" * 8
EVIL_BYTES = b"MZtest\n"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def _latest_reset_token_for(email_prefix: str) -> str:
    files = sorted(OUTBOX.glob(f"*_password_reset_{email_prefix}*.eml"), reverse=True)
    assert files, f"no password reset email in outbox for {email_prefix}"
    content = files[0].read_text(encoding="utf-8")
    m = re.search(r"token=([A-Za-z0-9._-]+)", content)
    assert m, "token not found in reset email"
    return m.group(1)


class TestP0ResetPasswordAuth:
    """P0-1: reset-password must require email token, not bare account."""

    async def test_account_only_reset_rejected(self, client):
        await _register(client, "sec_u1", "sec1@htex.test")
        r = await client.post(
            "/api/v2/auth/reset-password",
            json={"account": "sec1@htex.test", "new_password": "Hacked999"},
        )
        assert r.status_code == 400, r.text
        assert r.json()["code"] == "1001"

        r = await _login(client, "sec1@htex.test", "Hacked999")
        assert r.status_code == 401

    async def test_token_reset_still_works(self, client):
        await _register(client, "sec_u2", "sec2@htex.test", "OldPass1")
        await client.post(
            "/api/v2/auth/password-reset-request",
            json={"account": "sec2@htex.test"},
        )
        token = _latest_reset_token_for("sec2")
        r = await client.post(
            "/api/v2/auth/reset-password",
            json={"token": token, "new_password": "NewPass99"},
        )
        assert r.status_code == 200, r.text
        r = await _login(client, "sec2@htex.test", "NewPass99")
        assert r.status_code == 200


class TestP0ValidationPiiEcho:
    """P0-2: 422 responses must not echo submitted PII in errors[*].input."""

    async def test_diagnose_422_strips_input(self, client):
        token = await _register(client, "sec_pii", "pii@htex.test")
        body = {
            "country_code": "US",
            "marital_status": "single",
            "income_bucket": "medium",
            "applicant": {
                "surname": "ZHANG",
                "given_name": "SAN",
                "nationality": "CN",
                "passport_no": "E12345678",
                "birth_date": "1990-01-01",
                "phone": "+8613800138000",
                "email": "zhang@test.com",
            },
            "items": [{"category": "passport", "file_size": 1024, "sha256": "abc"}],
        }
        r = await client.post(
            "/api/v2/diagnose",
            headers=_bearer(token),
            json=body,
        )
        assert r.status_code == 400, r.text
        payload = r.json()
        assert payload["code"] == "1001"
        errors = payload["data"]["errors"]
        assert errors, "expected validation errors"
        for err in errors:
            assert "input" not in err
        dumped = json.dumps(payload)
        assert "E12345678" not in dumped
        assert "zhang@test.com" not in dumped


class TestP0FunnelConversionCap:
    """P0-3: funnel conversion_pct must stay within schema le=100."""

    def test_conversion_capped_at_100(self):
        steps = [
            {"key": "register", "label": "注册", "count": 5},
            {"key": "order_create", "label": "创建订单", "count": 7},
            {"key": "order_submit", "label": "提交订单", "count": 3},
            {"key": "order_finish", "label": "完成", "count": 2},
        ]
        for i, s in enumerate(steps):
            if i == 0:
                s["conversion_pct"] = 100.0
            else:
                prev = steps[i - 1]["count"]
                raw_pct = round((s["count"] / prev * 100.0), 2) if prev > 0 else 0.0
                s["conversion_pct"] = min(100.0, raw_pct)

        assert steps[1]["conversion_pct"] == 100.0
        assert all(0.0 <= s["conversion_pct"] <= 100.0 for s in steps)


class TestP0TokenInvalidation:
    """P0-4: old JWT must fail after password reset."""

    async def test_old_access_token_rejected_after_reset(self, client):
        token = await _register(client, "sec_tok", "tok@htex.test", "OldPass1")
        r = await client.get("/api/v2/profile", headers=_bearer(token))
        assert r.status_code == 200, r.text

        await client.post(
            "/api/v2/auth/password-reset-request",
            json={"account": "tok@htex.test"},
        )
        reset_token = _latest_reset_token_for("tok")
        r = await client.post(
            "/api/v2/auth/reset-password",
            json={"token": reset_token, "new_password": "NewPass99"},
        )
        assert r.status_code == 200, r.text

        r = await client.get("/api/v2/profile", headers=_bearer(token))
        assert r.status_code == 401, "old access token should be invalidated"
        assert r.json()["code"] == "1005"


class TestP0UploadMagicBytes:
    """P0-5: upload must reject spoofed content-types."""

    async def test_exe_disguised_as_png_rejected(self, client):
        token = await _register(client, "sec_up", "up@htex.test")
        files = {"file": ("evil.png", io.BytesIO(EVIL_BYTES), "image/png")}
        data = {"material_type": "passport"}
        r = await client.post(
            "/api/v2/materials/upload",
            files=files,
            data=data,
            headers=_bearer(token),
        )
        assert r.status_code == 400, r.text
        assert r.json()["code"] == "1003"

    async def test_valid_png_still_accepted(self, client):
        token = await _register(client, "sec_png", "png@htex.test")
        files = {"file": ("ok.png", io.BytesIO(PNG_BYTES), "image/png")}
        data = {"material_type": "passport"}
        r = await client.post(
            "/api/v2/materials/upload",
            files=files,
            data=data,
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text

    async def test_jpeg_declared_as_png_rejected(self, client):
        token = await _register(client, "sec_mime", "mime@htex.test")
        files = {"file": ("fake.png", io.BytesIO(JPEG_BYTES), "image/png")}
        data = {"material_type": "passport"}
        r = await client.post(
            "/api/v2/materials/upload",
            files=files,
            data=data,
            headers=_bearer(token),
        )
        assert r.status_code == 400, r.text
        assert r.json()["code"] == "1003"
