"""Integration tests for /api/v2/auth/* — V2 §4.1.

Coverage targets (auth module):
  - register: happy / phone-exists / weak-password / bad-sms / schema-violation
  - login:    happy / wrong-password / unknown-phone / disabled-account
  - sms-login:happy / auto-register-on-first-use
  - refresh:  happy / bad-token / revoked-token / wrong-type
  - send-code:happy / rate-limit (cooldown) / bad-purpose / bad-phone
"""
from __future__ import annotations

import pytest


# ----------------------------------------------------------------- #
# /send-code                                                          #
# ----------------------------------------------------------------- #
class TestSendCode:
    async def test_happy_returns_code_in_mock_mode(self, client):
        r = await client.post(
            "/api/v2/auth/send-code",
            json={"phone": "13900000001", "phone_country": "+86", "purpose": "register"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        assert body["data"]["code"] is not None
        assert len(body["data"]["code"]) == 6
        assert body["data"]["code"].isdigit()
        assert body["data"]["channel_txn_id"].startswith("mock_")

    async def test_invalid_phone_format(self, client):
        r = await client.post(
            "/api/v2/auth/send-code",
            json={"phone": "abc", "phone_country": "+86", "purpose": "register"},
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"

    async def test_invalid_phone_country(self, client):
        r = await client.post(
            "/api/v2/auth/send-code",
            json={"phone": "13900000001", "phone_country": "86", "purpose": "register"},
        )
        assert r.status_code == 400

    async def test_invalid_purpose(self, client):
        r = await client.post(
            "/api/v2/auth/send-code",
            json={"phone": "13900000001", "phone_country": "+86", "purpose": "nuke"},
        )
        assert r.status_code == 400

    async def test_cooldown_returns_2010(self, client):
        # 1st call OK
        r1 = await client.post(
            "/api/v2/auth/send-code",
            json={"phone": "13900000002", "phone_country": "+86", "purpose": "login"},
        )
        assert r1.status_code == 200
        # 2nd call within cooldown (1s in test) -> SMS_RATE_LIMIT
        r2 = await client.post(
            "/api/v2/auth/send-code",
            json={"phone": "13900000002", "phone_country": "+86", "purpose": "login"},
        )
        assert r2.status_code == 429
        assert r2.json()["code"] == "2010"


# ----------------------------------------------------------------- #
# /register                                                           #
# ----------------------------------------------------------------- #
class TestRegister:
    async def test_happy_path_201_with_jwt(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13800138001",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
                "nickname": "alice",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["code"] == "1000"
        data = body["data"]
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 7200
        assert data["access_token"].count(".") == 2  # JWT shape
        assert data["refresh_token"].count(".") == 2
        assert data["user"]["phone"] == "13800138001"
        assert data["user"]["nickname"] == "alice"
        assert data["user"]["status"] == "active"

    async def test_duplicate_phone_2003(self, client):
        body = {
            "phone": "13800138002",
            "phone_country": "+86",
            "password": "abc12345",
            "sms_code": "123456",
        }
        r1 = await client.post("/api/v2/auth/register", json=body)
        assert r1.status_code == 201

        r2 = await client.post("/api/v2/auth/register", json=body)
        assert r2.status_code == 409
        assert r2.json()["code"] == "2003"

    async def test_weak_password_2004(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13800138003",
                "phone_country": "+86",
                "password": "abcdefgh",  # no digit
                "sms_code": "123456",
            },
        )
        assert r.status_code == 422
        assert r.json()["code"] == "2004"

    async def test_short_password(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13800138004",
                "phone_country": "+86",
                "password": "ab1",  # too short
                "sms_code": "123456",
            },
        )
        assert r.status_code == 400  # Pydantic min_length triggers 1001
        assert r.json()["code"] == "1001"

    async def test_sms_code_wrong_format(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13800138005",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "12ab56",
            },
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"

    async def test_missing_field(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={"phone": "13800138006", "phone_country": "+86"},
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"


# ----------------------------------------------------------------- #
# /login                                                              #
# ----------------------------------------------------------------- #
class TestLogin:
    async def test_happy(self, client):
        # register first
        await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13911110001",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        r = await client.post(
            "/api/v2/auth/login",
            json={"phone": "13911110001", "phone_country": "+86", "password": "abc12345"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "1000"
        assert body["data"]["access_token"]

    async def test_wrong_password_2001(self, client):
        await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13911110002",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        r = await client.post(
            "/api/v2/auth/login",
            json={"phone": "13911110002", "phone_country": "+86", "password": "wrong"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_unknown_phone_2001(self, client):
        r = await client.post(
            "/api/v2/auth/login",
            json={"phone": "13911110099", "phone_country": "+86", "password": "abc12345"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_disabled_account_2005(self, client):
        # register, then flip status to 'disabled' in DB
        from app.core.db import AsyncSessionLocal
        from app.models.user import User
        from sqlalchemy import select

        await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13911110003",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        async with AsyncSessionLocal() as session:
            user = await session.scalar(
                select(User).where(User.phone == "13911110003")
            )
            user.status = "disabled"
            await session.commit()

        r = await client.post(
            "/api/v2/auth/login",
            json={"phone": "13911110003", "phone_country": "+86", "password": "abc12345"},
        )
        assert r.status_code == 403
        assert r.json()["code"] == "2005"


# ----------------------------------------------------------------- #
# /sms-login                                                          #
# ----------------------------------------------------------------- #
class TestSmsLogin:
    async def test_happy_existing_user(self, client):
        # register
        await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13922220001",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        r = await client.post(
            "/api/v2/auth/sms-login",
            json={"phone": "13922220001", "phone_country": "+86", "sms_code": "999999"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["access_token"]

    async def test_auto_register_on_first_use(self, client):
        r = await client.post(
            "/api/v2/auth/sms-login",
            json={"phone": "13922220002", "phone_country": "+86", "sms_code": "111111"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["user"]["phone"] == "13922220002"
        assert body["data"]["user"]["status"] == "active"

    async def test_invalid_sms_format(self, client):
        r = await client.post(
            "/api/v2/auth/sms-login",
            json={"phone": "13922220003", "phone_country": "+86", "sms_code": "abc"},
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"


# ----------------------------------------------------------------- #
# /refresh                                                            #
# ----------------------------------------------------------------- #
class TestRefresh:
    async def _register_and_get_refresh(self, client, phone: str) -> str:
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": phone,
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        return r.json()["data"]["refresh_token"]

    async def test_happy_returns_new_pair(self, client):
        old_refresh = await self._register_and_get_refresh(client, "13933330001")
        r = await client.post("/api/v2/auth/refresh", json={"refresh_token": old_refresh})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["data"]["access_token"]
        assert body["data"]["refresh_token"]
        # Old refresh token was rotated — it should now be invalid.
        r2 = await client.post("/api/v2/auth/refresh", json={"refresh_token": old_refresh})
        assert r2.status_code == 401
        assert r2.json()["code"] in ("2006", "2007")

    async def test_invalid_token_2006(self, client):
        r = await client.post(
            "/api/v2/auth/refresh", json={"refresh_token": "not-a-jwt"}
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2006"

    async def test_wrong_token_type(self, client):
        # Use an access token as a refresh token
        reg = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13933330002",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        access = reg.json()["data"]["access_token"]
        r = await client.post(
            "/api/v2/auth/refresh", json={"refresh_token": access}
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2006"


# ----------------------------------------------------------------- #
# Edge: health & root                                                  #
# ----------------------------------------------------------------- #
class TestHealth:
    async def test_health_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_root(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        assert "docs" in r.json()


# ----------------------------------------------------------------- #
# Service-layer / integration extras to push coverage                #
# ----------------------------------------------------------------- #
class TestServiceLayerExtras:
    async def test_register_creates_audit_log(self, client):
        await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13944440001",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        # Inspect DB for the audit row
        from app.core.db import AsyncSessionLocal
        from app.models.audit_log import AuditLog
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as s:
            row = await s.scalar(
                select(AuditLog)
                .where(AuditLog.action == "user.register")
                .order_by(desc(AuditLog.id))
                .limit(1)
            )
            assert row is not None
            assert row.actor_type == "user"
            assert row.actor_id == 1  # first user

    async def test_login_updates_last_login(self, client):
        await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13944440002",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        r = await client.post(
            "/api/v2/auth/login",
            json={"phone": "13944440002", "phone_country": "+86", "password": "abc12345"},
        )
        assert r.status_code == 200
        # Verify last_login_at got set
        from app.core.db import AsyncSessionLocal
        from app.models.user import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as s:
            user = await s.scalar(select(User).where(User.phone == "13944440002"))
            assert user is not None
            assert user.last_login_at is not None

    async def test_login_no_password_set_2001(self, client):
        # SMS-only registered user has password_hash=None -> cannot password-login
        await client.post(
            "/api/v2/auth/sms-login",
            json={"phone": "13944440003", "phone_country": "+86", "sms_code": "123456"},
        )
        r = await client.post(
            "/api/v2/auth/login",
            json={"phone": "13944440003", "phone_country": "+86", "password": "whatever"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_register_with_custom_language(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13944440004",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
                "language_pref": "en",
            },
        )
        assert r.status_code == 201
        assert r.json()["data"]["user"]["language_pref"] == "en"

    async def test_register_default_nickname(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13944440005",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        assert r.status_code == 201
        # Default nickname is "user_<last4>"
        assert r.json()["data"]["user"]["nickname"] == "user_0005"

    async def test_refresh_audit_log(self, client):
        reg = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13944440006",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
        )
        refresh = reg.json()["data"]["refresh_token"]
        await client.post("/api/v2/auth/refresh", json={"refresh_token": refresh})

        from app.core.db import AsyncSessionLocal
        from app.models.audit_log import AuditLog
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as s:
            row = await s.scalar(
                select(AuditLog)
                .where(AuditLog.action == "user.refresh")
                .order_by(desc(AuditLog.id))
                .limit(1)
            )
            assert row is not None

    async def test_user_agent_and_device_fingerprint_recorded(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "phone": "13944440007",
                "phone_country": "+86",
                "password": "abc12345",
                "sms_code": "123456",
            },
            headers={
                "User-Agent": "visa-mvp-test/1.0",
                "X-Device-Fingerprint": "device-abc-123",
            },
        )
        assert r.status_code == 201
        from app.core.db import AsyncSessionLocal
        from app.models.user_session import UserSession
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as s:
            row = await s.scalar(
                select(UserSession).order_by(desc(UserSession.id)).limit(1)
            )
            assert row is not None
            assert row.user_agent == "visa-mvp-test/1.0"
            assert row.device_fingerprint == "device-abc-123"


# ----------------------------------------------------------------- #
# Direct service-level unit tests (sync, so coverage tracks lines)   #
# ----------------------------------------------------------------- #
class TestAuthServiceSync:
    """These tests run synchronously against the AuthService to push
    coverage of the service layer above 80%, since pytest-cov has known
    issues tracking async coverage across event loops in some setups."""

    def test_register_user_not_found_in_refresh(self):
        """Cover the `if user is None: raise USER_NOT_FOUND` branch."""
        # Build a refresh token for a user that does not exist.
        from app.core.security import create_refresh_token
        from app.core.errors import ErrorCode
        from app.services.auth_service import AuthService
        from app.core.db import AsyncSessionLocal
        import asyncio

        async def go():
            async with AsyncSessionLocal() as s:
                # Forge a refresh token for a phantom user id 99999
                rt, _ = create_refresh_token(99999)
                svc = AuthService(s)
                try:
                    await svc.refresh(refresh_token=rt, info={"ip": "127.0.0.1"})
                except Exception as exc:
                    assert exc.code == ErrorCode.USER_NOT_FOUND
                    return
                raise AssertionError("expected USER_NOT_FOUND")

        asyncio.run(go())

    def test_refresh_session_revoked_branch(self):
        """Cover the `if old_session is None or revoked` branch."""
        from app.core.security import create_refresh_token
        from app.core.errors import ErrorCode
        from app.services.auth_service import AuthService
        from app.core.db import AsyncSessionLocal
        from app.models.user import User
        from app.models.user_session import UserSession
        import asyncio
        from datetime import datetime, timezone

        async def go():
            async with AsyncSessionLocal() as s:
                # Create a real user
                u = User(
                    phone="13888880001",
                    phone_country="+86",
                    password_hash=None,
                    nickname="u1",
                    status="active",
                )
                s.add(u)
                await s.flush()
                # Create a refresh token, then revoke its session row
                rt, exp = create_refresh_token(u.id)
                import hashlib
                sess = UserSession(
                    user_id=u.id,
                    refresh_token_hash=hashlib.sha256(rt.encode()).hexdigest(),
                    expires_at=exp.replace(tzinfo=None),
                    revoked_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                s.add(sess)
                await s.commit()

                svc = AuthService(s)
                try:
                    await svc.refresh(refresh_token=rt, info={"ip": "127.0.0.1"})
                except Exception as exc:
                    assert exc.code == ErrorCode.REFRESH_TOKEN_INVALID
                    return
                raise AssertionError("expected REFRESH_TOKEN_INVALID")

        asyncio.run(go())

    def test_sms_service_enforce_daily_limit(self):
        """Cover the daily_limit branch of SmsService._enforce_rate_limit."""
        from app.core.errors import ErrorCode
        from app.services.sms_service import SmsService
        from app.core.db import AsyncSessionLocal
        from app.models.sms_code import SmsCode
        from datetime import datetime, timezone, timedelta
        import asyncio

        async def go():
            async with AsyncSessionLocal() as s:
                # Pre-insert 9999 rows in the last 24h to hit the daily cap (10000)
                phone = "13800000011"
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                rows = [
                    SmsCode(
                        phone=phone,
                        phone_country="+86",
                        code_hash=f"h{i}",
                        purpose="login",
                        expires_at=now + timedelta(seconds=300),
                        send_count=1,
                        created_at=now - timedelta(seconds=i),
                    )
                    for i in range(10000)
                ]
                s.add_all(rows)
                await s.commit()

                svc = SmsService(s)
                try:
                    await svc.send_code(phone, "+86", "login")
                except Exception as exc:
                    assert exc.code == ErrorCode.SMS_RATE_LIMIT
                    return
                raise AssertionError("expected SMS_RATE_LIMIT (daily)")

        asyncio.run(go())

    def test_security_validate_password_strength_short(self):
        from app.core.security import validate_password_strength
        from app.core.errors import ErrorCode

        try:
            validate_password_strength("abc12")  # too short
        except Exception as exc:
            assert exc.code == ErrorCode.PASSWORD_TOO_WEAK
            return
        raise AssertionError("expected PASSWORD_TOO_WEAK (short)")

    def test_security_validate_password_strength_no_digit(self):
        from app.core.security import validate_password_strength
        from app.core.errors import ErrorCode

        try:
            validate_password_strength("abcdefgh")  # no digit
        except Exception as exc:
            assert exc.code == ErrorCode.PASSWORD_TOO_WEAK
            return
        raise AssertionError("expected PASSWORD_TOO_WEAK (no digit)")

    def test_security_decode_token_wrong_type(self):
        from app.core.security import decode_token, create_access_token, TOKEN_TYPE_REFRESH
        from app.core.errors import ErrorCode

        access, _ = create_access_token(1)
        try:
            decode_token(access, TOKEN_TYPE_REFRESH)
        except Exception as exc:
            assert exc.code == ErrorCode.REFRESH_TOKEN_INVALID
            return
        raise AssertionError("expected REFRESH_TOKEN_INVALID (wrong type)")

    def test_sms_channel_factory(self):
        from app.services.sms.factory import get_sms_channel
        ch = get_sms_channel()
        assert ch.__class__.__name__ == "MockSMSChannel"

    def test_payment_factory(self):
        from app.services.payment.factory import get_payment_adapter
        a = get_payment_adapter()
        assert a.__class__.__name__ == "MockPaymentAdapter"
