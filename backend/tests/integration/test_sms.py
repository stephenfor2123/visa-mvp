"""Integration tests for /api/v2/sms/* — B-W6-1 standalone SMS service.

Covers (3 cases):
  - test_sms_factory: MockSmsProvider factory + singleton behavior
  - test_send_code_mock: /api/v2/sms/send returns 200 + message_id + code,
                         provider store contains a live entry
  - test_verify_code:   /api/v2/sms/verify succeeds / fails / expires

Locked behavior:
  - POST /api/v2/sms/send → {code, message_id, expires_in, template_id}
  - POST /api/v2/sms/verify (correct) → {verified:true, access_token}
  - POST /api/v2/sms/verify (wrong)  → 2002 SMS_CODE_INVALID
  - POST /api/v2/sms/verify (expired) → 2008 SMS_CODE_EXPIRED
"""
from __future__ import annotations

import time

import pytest

from app.services.sms_provider import (
    CodeExpired,
    CodeMismatch,
    MockSmsProvider,
    NoCodeOnFile,
    get_sms_provider,
    reset_sms_provider_for_tests,
)


# ----------------------------------------------------------------- #
# Fixtures                                                            #
# ----------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _isolate_provider():
    """Each test gets a fresh in-memory store."""
    reset_sms_provider_for_tests()
    yield
    reset_sms_provider_for_tests()


# ----------------------------------------------------------------- #
# 1. test_sms_factory                                                 #
# ----------------------------------------------------------------- #
class TestSmsFactory:
    def test_factory_returns_mock_singleton(self):
        p1 = get_sms_provider()
        p2 = get_sms_provider()
        assert isinstance(p1, MockSmsProvider)
        assert p1 is p2, "factory must return the same singleton across calls"

    def test_factory_returns_fresh_after_reset(self):
        p1 = get_sms_provider()
        reset_sms_provider_for_tests()
        p2 = get_sms_provider()
        assert p1 is not p2, "reset_sms_provider_for_tests must drop the singleton"

    def test_mock_provider_rejects_bad_config(self):
        with pytest.raises(ValueError):
            MockSmsProvider(ttl_seconds=0)
        with pytest.raises(ValueError):
            MockSmsProvider(code_length=3)


# ----------------------------------------------------------------- #
# 2. test_send_code_mock                                              #
# ----------------------------------------------------------------- #
class TestSendCodeMock:
    async def test_send_returns_message_id_and_code(self, client):
        r = await client.post(
            "/api/v2/sms/send",
            json={"phone": "13800138001", "phone_country": "+86", "purpose": "login"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        data = body["data"]
        assert data["message_id"].startswith("mock_")
        assert data["code"] and data["code"].isdigit() and len(data["code"]) == 6
        assert data["expires_in"] == 300
        assert data["purpose"] == "login"
        assert data["phone"] == "13800138001"
        assert data["phone_country"] == "+86"
        assert data["template_id"] == "mock_default"

    async def test_send_stores_code_in_provider(self, client):
        provider = get_sms_provider()
        r = await client.post(
            "/api/v2/sms/send",
            json={"phone": "13800138002", "phone_country": "+86", "purpose": "register"},
        )
        code = r.json()["data"]["code"]
        # Provider's internal store now has a live entry — verify_code
        # against the same (phone, purpose) succeeds.
        ok = await provider.verify_code(
            phone="13800138002", phone_country="+86", code=code, purpose="register",
        )
        assert ok is True

    async def test_send_rejects_invalid_purpose(self, client):
        r = await client.post(
            "/api/v2/sms/send",
            json={"phone": "13800138003", "phone_country": "+86", "purpose": "bogus"},
        )
        # Pydantic validation surfaces first as a 400 with INVALID_PARAMS.
        assert r.status_code == 400
        assert r.json()["code"] == "1001"


# ----------------------------------------------------------------- #
# 3. test_verify_code                                                 #
# ----------------------------------------------------------------- #
class TestVerifyCode:
    async def _send(self, client, phone="13800138010", purpose="login"):
        r = await client.post(
            "/api/v2/sms/send",
            json={"phone": phone, "phone_country": "+86", "purpose": purpose},
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]["code"]

    async def test_verify_correct_returns_jwt(self, client):
        code = await self._send(client)
        r = await client.post(
            "/api/v2/sms/verify",
            json={"phone": "13800138010", "phone_country": "+86", "purpose": "login", "code": code},
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["verified"] is True
        assert data["access_token"], "mock mode must mint a JWT"
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] > 0
        # Header looks like a JWT (3 dot-separated base64 segments).
        assert data["access_token"].count(".") == 2

    async def test_verify_wrong_code_returns_2002(self, client):
        await self._send(client)
        r = await client.post(
            "/api/v2/sms/verify",
            json={"phone": "13800138010", "phone_country": "+86", "purpose": "login", "code": "000000"},
        )
        assert r.status_code == 422
        assert r.json()["code"] == "2002"  # SMS_CODE_INVALID

    async def test_verify_no_code_on_file_returns_2002(self, client):
        # Never called /send first.
        r = await client.post(
            "/api/v2/sms/verify",
            json={"phone": "13800138999", "phone_country": "+86", "purpose": "login", "code": "123456"},
        )
        assert r.status_code == 422
        assert r.json()["code"] == "2002"

    async def test_verify_expired_returns_2008(self, client, monkeypatch):
        """Force expiry by patching the provider's TTL to 0 + waiting 1s.

        We monkeypatch time.monotonic() inside the provider module — that
        keeps the rest of the codebase unaffected.
        """
        provider = get_sms_provider()
        # Shorten TTL so a real sleep is enough.
        provider._ttl = 1
        await self._send(client, phone="13800138020", purpose="login")
        time.sleep(1.1)  # let TTL elapse

        r = await client.post(
            "/api/v2/sms/verify",
            json={"phone": "13800138020", "phone_country": "+86", "purpose": "login", "code": "123456"},
        )
        assert r.status_code == 422
        assert r.json()["code"] == "2008"  # SMS_CODE_EXPIRED

    async def test_verify_is_one_shot(self, client):
        """A successful verify must consume the OTP — second call → 2002."""
        phone = "13800138050"
        code = await self._send(client, phone=phone)
        r1 = await client.post(
            "/api/v2/sms/verify",
            json={"phone": phone, "phone_country": "+86", "purpose": "login", "code": code},
        )
        assert r1.status_code == 200, r1.text
        r2 = await client.post(
            "/api/v2/sms/verify",
            json={"phone": phone, "phone_country": "+86", "purpose": "login", "code": code},
        )
        assert r2.status_code == 422
        assert r2.json()["code"] == "2002"

    async def test_status_endpoint_returns_unknown_for_unknown_id(self, client):
        r = await client.get("/api/v2/sms/mock_does_not_exist")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "unknown"
        assert data["message_id"] == "mock_does_not_exist"

    async def test_status_endpoint_returns_sent_for_live_id(self, client):
        send = await client.post(
            "/api/v2/sms/send",
            json={"phone": "13800138040", "phone_country": "+86", "purpose": "reset"},
        )
        message_id = send.json()["data"]["message_id"]
        r = await client.get(f"/api/v2/sms/{message_id}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "sent"
        assert data["phone"] == "13800138040"
        assert data["purpose"] == "reset"

    async def test_template_register_endpoint_round_trip(self, client):
        r = await client.post(
            "/api/v2/sms/template",
            json={
                "template_id": "tpl_welcome_en",
                "purpose": "register",
                "locale": "en-US",
                "body": "Welcome! Your code is {code}.",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["template_id"] == "tpl_welcome_en"
        assert data["locale"] == "en-US"
        # get_template reflects the new entry
        provider = get_sms_provider()
        body = await provider.get_template("register", "en-US")
        assert body == "Welcome! Your code is {code}."


# ----------------------------------------------------------------- #
# Direct provider-layer tests (no HTTP)                              #
# ----------------------------------------------------------------- #
class TestProviderDirect:
    async def test_provider_raises_specific_errors(self):
        provider = MockSmsProvider()
        # No code on file
        with pytest.raises(NoCodeOnFile):
            await provider.verify_code("123", "+86", "123456", "login")
        # After send, wrong code → CodeMismatch
        await provider.send_sms("123", "+86", "login")
        with pytest.raises(CodeMismatch):
            await provider.verify_code("123", "+86", "000000", "login")
        # Re-send then expire via short TTL
        provider._ttl = 1
        await provider.send_sms("123", "+86", "login")
        time.sleep(1.1)
        with pytest.raises(CodeExpired):
            await provider.verify_code("123", "+86", "123456", "login")