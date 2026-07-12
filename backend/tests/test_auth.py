"""Integration tests for /api/v2/auth/* — V2 §4.1.

Coverage targets (auth module):
  - register: happy / email-exists / weak-password / bad-email / schema-violation
  - login:    happy / wrong-password / unknown-account / disabled-account
  - refresh:  happy / bad-token / revoked-token / wrong-type
"""
from __future__ import annotations

import pytest


# ----------------------------------------------------------------- #
# /register  (W26: username + email + password)                      #
# ----------------------------------------------------------------- #
class TestRegister:
    async def test_happy_path_201_with_jwt(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "testalice1",
                "email": "alice1@htex.test",
                "password": "abc12345",
                "email_code": "123456",
                "nickname": "Alice",
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
        assert data["user"]["username"] == "testalice1"
        assert data["user"]["email"] == "alice1@htex.test"
        assert data["user"]["nickname"] == "Alice"
        assert data["user"]["status"] == "active"

    async def test_duplicate_email_2003(self, client):
        body = {
            "username": "testbob2a",
            "email": "bob2@htex.test",
            "password": "abc12345",
            "email_code": "123456",
        }
        r1 = await client.post("/api/v2/auth/register", json=body)
        assert r1.status_code == 201

        # Different username but same email → 409 / 2003
        r2 = await client.post(
            "/api/v2/auth/register",
            json={**body, "username": "testbob2b"},
        )
        assert r2.status_code == 409
        assert r2.json()["code"] == "2003"

    async def test_duplicate_username_2003(self, client):
        body = {
            "username": "testcharlie3",
            "email": "charlie3a@htex.test",
            "password": "abc12345",
            "email_code": "123456",
        }
        r1 = await client.post("/api/v2/auth/register", json=body)
        assert r1.status_code == 201

        # Same username but different email → 409 / 2003
        r2 = await client.post(
            "/api/v2/auth/register",
            json={**body, "email": "charlie3b@htex.test"},
        )
        assert r2.status_code == 409
        assert r2.json()["code"] == "2003"

    async def test_weak_password_2004(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "testdave4",
                "email": "dave4@htex.test",
                "password": "abcdefgh",  # no digit → weak
                "email_code": "123456",
            },
        )
        assert r.status_code == 422
        assert r.json()["code"] == "2004"

    async def test_short_password(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "testeve5",
                "email": "eve5@htex.test",
                "password": "ab1",  # too short
                "email_code": "123456",
            },
        )
        assert r.status_code == 400  # Pydantic min_length triggers 1001
        assert r.json()["code"] == "1001"

    async def test_bad_email_format(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "testfrank6",
                "email": "not-an-email",
                "password": "abc12345",
                "email_code": "123456",
            },
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"

    async def test_missing_field(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={"username": "testgrace7"},  # missing email + password
        )
        assert r.status_code == 400
        assert r.json()["code"] == "1001"


# ----------------------------------------------------------------- #
# /login  (W26: account = email OR username)                         #
# ----------------------------------------------------------------- #
class TestLogin:
    async def test_happy(self, client):
        await client.post(
            "/api/v2/auth/register",
            json={"username": "loginuser1", "email": "loginuser1@htex.test", "password": "abc12345", "email_code": "123456"},
    )
        r = await client.post(
            "/api/v2/auth/login",
            json={"account": "loginuser1", "password": "abc12345"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == "1000"
        assert body["data"]["access_token"]

    async def test_login_by_email(self, client):
        await client.post(
            "/api/v2/auth/register",
            json={"username": "loginuser2", "email": "loginuser2@htex.test", "password": "abc12345", "email_code": "123456"},
    )
        r = await client.post(
            "/api/v2/auth/login",
            json={"account": "loginuser2@htex.test", "password": "abc12345"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"

    async def test_wrong_password_2001(self, client):
        await client.post(
            "/api/v2/auth/register",
            json={"username": "loginuser3", "email": "loginuser3@htex.test", "password": "abc12345", "email_code": "123456"},
    )
        r = await client.post(
            "/api/v2/auth/login",
            json={"account": "loginuser3", "password": "wrongpassword1"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_unknown_account_2001(self, client):
        r = await client.post(
            "/api/v2/auth/login",
            json={"account": "nobody_exists_99", "password": "abc12345"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_disabled_account_2005(self, client):
        from app.core.db import AsyncSessionLocal
        from app.models.user import User
        from sqlalchemy import select

        await client.post(
            "/api/v2/auth/register",
            json={"username": "loginuser4", "email": "loginuser4@htex.test", "password": "abc12345", "email_code": "123456"},
    )
        async with AsyncSessionLocal() as session:
            user = await session.scalar(
                select(User).where(User.email == "loginuser4@htex.test")
            )
            user.status = "disabled"
            await session.commit()

        r = await client.post(
            "/api/v2/auth/login",
            json={"account": "loginuser4", "password": "abc12345"},
        )
        assert r.status_code == 403
        assert r.json()["code"] == "2005"


# ----------------------------------------------------------------- #
# /refresh                                                            #
# ----------------------------------------------------------------- #
class TestRefresh:
    async def _register_and_get_refresh(self, client, username: str) -> str:
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": username,
                "email": f"{username}@htex.test",
                "password": "abc12345",
                "email_code": "123456",
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["data"]["refresh_token"]

    async def test_happy_returns_new_pair(self, client):
        old_refresh = await self._register_and_get_refresh(client, "refreshuser1")
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
                "username": "refreshuser2",
                "email": "refreshuser2@htex.test",
                "password": "abc12345",
                "email_code": "123456",
            },
        )
        assert reg.status_code == 201, reg.text
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
                "username": "audituser1",
                "email": "audituser1@htex.test",
                "password": "abc12345",
                "email_code": "123456",
            },
        )
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

    async def test_login_updates_last_login(self, client):
        await client.post(
            "/api/v2/auth/register",
            json={
                "username": "audituser2",
                "email": "audituser2@htex.test",
                "password": "abc12345",
                "email_code": "123456",
            },
        )
        r = await client.post(
            "/api/v2/auth/login",
            json={"account": "audituser2", "password": "abc12345"},
        )
        assert r.status_code == 200
        from app.core.db import AsyncSessionLocal
        from app.models.user import User
        from sqlalchemy import select

        async with AsyncSessionLocal() as s:
            user = await s.scalar(select(User).where(User.email == "audituser2@htex.test"))
            assert user is not None
            assert user.last_login_at is not None

    async def test_register_with_custom_language(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "audituser4",
                "email": "audituser4@htex.test",
                "password": "abc12345",
                "email_code": "123456",
                "language_pref": "en",
            },
        )
        assert r.status_code == 201
        assert r.json()["data"]["user"]["language_pref"] == "en"

    async def test_register_default_nickname(self, client):
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "audituser5",
                "email": "audituser5@htex.test",
                "password": "abc12345",
                "email_code": "123456",
            },
        )
        assert r.status_code == 201
        # Default nickname = "user_" + last 4 chars of username = "user_ser5"
        assert r.json()["data"]["user"]["nickname"] == "user_ser5"

    async def test_refresh_audit_log(self, client):
        reg = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "audituser6",
                "email": "audituser6@htex.test",
                "password": "abc12345",
                "email_code": "123456",
            },
        )
        assert reg.status_code == 201, reg.text
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
                "username": "audituser7",
                "email": "audituser7@htex.test",
                "password": "abc12345",
                "email_code": "123456",
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
# Direct service-layer tests — use app fixture so DB schema exists   #
# ----------------------------------------------------------------- #
class TestAuthServiceSync:
    """Service-layer tests that exercise branches not easily hit via the HTTP API.
    Using app fixture ensures the test DB schema is created before each test."""

    async def test_register_user_not_found_in_refresh(self, app):
        """Cover the `if user is None: raise USER_NOT_FOUND` branch."""
        from app.core.security import create_refresh_token
        from app.core.errors import ErrorCode
        from app.services.auth_service import AuthService
        from app.core.db import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            rt, _ = create_refresh_token(99999)
            svc = AuthService(s)
            raised = False
            try:
                await svc.refresh(refresh_token=rt, info={"ip": "127.0.0.1"})
            except Exception as exc:
                raised = True
                assert exc.code == ErrorCode.USER_NOT_FOUND
            assert raised, "expected USER_NOT_FOUND"

    async def test_refresh_session_revoked_branch(self, app):
        """Cover the `if old_session is None or revoked` branch."""
        import hashlib
        from datetime import datetime, timezone

        from app.core.security import create_refresh_token
        from app.core.errors import ErrorCode
        from app.services.auth_service import AuthService
        from app.core.db import AsyncSessionLocal
        from app.models.user import User
        from app.models.user_session import UserSession

        async with AsyncSessionLocal() as s:
            u = User(
                email="revoke_test@test.local",
                username="revoketest1",
                password_hash=None,
                nickname="u1",
                status="active",
            )
            s.add(u)
            await s.flush()
            rt, exp = create_refresh_token(u.id)
            sess = UserSession(
                user_id=u.id,
                refresh_token_hash=hashlib.sha256(rt.encode()).hexdigest(),
                expires_at=exp.replace(tzinfo=None),
                revoked_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            s.add(sess)
            await s.commit()

            svc = AuthService(s)
            raised = False
            try:
                await svc.refresh(refresh_token=rt, info={"ip": "127.0.0.1"})
            except Exception as exc:
                raised = True
                assert exc.code == ErrorCode.REFRESH_TOKEN_INVALID
            assert raised, "expected REFRESH_TOKEN_INVALID"

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

    def test_payment_factory(self):
        from app.services.payment.factory import get_payment_adapter
        a = get_payment_adapter()
        assert a.__class__.__name__ == "MockPaymentAdapter"
