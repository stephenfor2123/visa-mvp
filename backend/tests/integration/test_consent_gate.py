"""Integration tests for the GDPR sensitive-processing consent gate.

The materials upload / OCR / LLM endpoints refuse to process personal data
until the user has granted purpose-bound consent (Art.7).  These tests run
against the *real* gate (the global autouse bypass in conftest is disabled
via the ``real_consent`` marker).

Covers:
  - upload without consent → 403 CONSENT_REQUIRED (code 2017)
  - grant consent via POST /v2/profile/consents → subsequent upload 201
  - revoke consent → upload blocked again
"""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.real_consent

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register_login(client, phone: str) -> str:
    uname = f"u{phone}"
    email = f"{phone}@test.local"
    pwd = "Test1234"
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": uname,
            "email": email,
            "password": pwd,
            "email_code": "123456",
            "age_confirmed_16": True,
        },
    )
    r = await client.post(
        "/api/v2/auth/login",
        json={"account": email, "password": pwd},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _upload(client, token: str):
    files = {"file": ("passport.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
    return await client.post(
        "/api/v2/materials/upload",
        files=files,
        data={"material_type": "passport"},
        headers=_bearer(token),
    )


class TestSensitiveConsentGate:
    async def test_upload_without_consent_is_blocked(self, client):
        token = await _register_login(client, "13900000001")
        r = await _upload(client, token)
        assert r.status_code == 403, r.text
        assert r.json()["code"] == "2017"

    async def test_upload_after_consent_granted(self, client):
        token = await _register_login(client, "13900000002")

        grant = await client.post(
            "/api/v2/profile/consents",
            json={"purpose": "sensitive_upload", "version": "v1"},
            headers=_bearer(token),
        )
        assert grant.status_code == 200, grant.text

        r = await _upload(client, token)
        assert r.status_code == 201, r.text
        assert r.json()["data"]["material"]["id"] > 0

    async def test_upload_blocked_again_after_revoke(self, client):
        token = await _register_login(client, "13900000003")

        await client.post(
            "/api/v2/profile/consents",
            json={"purpose": "sensitive_upload", "version": "v1"},
            headers=_bearer(token),
        )
        ok = await _upload(client, token)
        assert ok.status_code == 201, ok.text

        revoke = await client.post(
            "/api/v2/profile/consents/revoke",
            json={"purpose": "sensitive_upload", "version": "v1"},
            headers=_bearer(token),
        )
        assert revoke.status_code == 200, revoke.text

        blocked = await _upload(client, token)
        assert blocked.status_code == 403, blocked.text
        assert blocked.json()["code"] == "2017"
