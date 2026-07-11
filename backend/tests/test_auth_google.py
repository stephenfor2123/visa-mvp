"""
Google OAuth login — /api/v2/auth/google (V2 §4.1).

Coverage targets:
  - happy new-user:    Google id_token → auto-register + JWT pair
  - happy returning:   existing google_sub → login + JWT pair (no new row)
  - email link:        existing password user (same email) → bind google_sub
  - invalid token:     google-auth raises → AUTH_INVALID_CREDENTIALS
  - not configured:    GOOGLE_CLIENT_ID unset → SERVER_ERROR
  - disabled user:     status=disabled → ACCOUNT_DISABLED

Mock strategy: `google.oauth2.id_token.verify_oauth2_token` is patched
per-test so we don't depend on network or Google's certs.
"""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.errors import ErrorCode
from app.models.user import User


def _make_idinfo(sub: str, email: str = "", name: str = "", picture: str = ""):
    """Synthetic Google idinfo payload returned by verify_oauth2_token."""
    return {
        "iss": "https://accounts.google.com",
        "sub": sub,
        "email": email,
        "email_verified": bool(email),
        "name": name,
        "picture": picture,
        "aud": "test-google-client-id",
    }


@pytest.fixture
def google_client_id_set(monkeypatch):
    """Set settings.google_client_id for the duration of a single test.

    `get_settings()` is lru_cached, so we patch the cached instance directly.
    """
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", "test-google-client-id")
    yield "test-google-client-id"
    # monkeypatch restores automatically


class TestGoogleAuth:
    async def test_happy_new_user(self, client, google_client_id_set):
        """First-time Google login → auto-register with username 'g_<last8sub>'."""
        idinfo = _make_idinfo(
            sub="1234567890abcdef",
            email="newuser@gmail.com",
            name="New User",
            picture="https://lh3.googleusercontent.com/avatar.png",
        )
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r = await client.post(
                "/api/v2/auth/google",
                json={"id_token": "fake.jwt.token"},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        data = body["data"]
        assert data["access_token"].count(".") == 2
        assert data["refresh_token"].count(".") == 2
        assert data["user"]["email"] == "newuser@gmail.com"
        assert data["user"]["nickname"] == "New User"
        assert data["user"]["status"] == "active"
        assert data["user"]["username"].startswith("g_")

        # DB row exists with google_sub bound
        async with AsyncSessionLocal() as s:
            u = await s.scalar(select(User).where(User.email == "newuser@gmail.com"))
            assert u is not None
            assert u.google_sub == "1234567890abcdef"
            assert u.password_hash is None  # no password for OAuth-only users

    async def test_returning_user_no_re_register(self, client, google_client_id_set):
        """Same Google sub second time → just issue new JWT, no duplicate row."""
        idinfo = _make_idinfo(
            sub="aaaa1111bbbb2222",
            email="returning@gmail.com",
            name="Returning User",
        )
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r1 = await client.post("/api/v2/auth/google", json={"id_token": "fake.jwt.1"})
            r2 = await client.post("/api/v2/auth/google", json={"id_token": "fake.jwt.2"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["data"]["user"]["id"] == r2.json()["data"]["user"]["id"]

        # Only one row in DB
        async with AsyncSessionLocal() as s:
            rows = (await s.execute(
                select(User).where(User.google_sub == "aaaa1111bbbb2222")
            )).scalars().all()
            assert len(rows) == 1

    async def test_email_link_to_existing_password_user(self, client, google_client_id_set):
        """Existing password user with same email → bind google_sub to same row."""
        # Pre-register via password flow
        reg = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "linktarget",
                "email": "linktarget@htex.test",
                "password": "abc12345",
                "nickname": "Link Target",
            },
        )
        assert reg.status_code == 201
        user_id_before = reg.json()["data"]["user"]["id"]

        # Now log in with Google using the SAME email
        idinfo = _make_idinfo(
            sub="cccc3333dddd4444",
            email="linktarget@htex.test",
            name="Link Target",
            picture="https://example.com/pic.png",
        )
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r = await client.post("/api/v2/auth/google", json={"id_token": "fake.jwt.3"})
        assert r.status_code == 200
        body = r.json()
        # Same user id — not a duplicate
        assert body["data"]["user"]["id"] == user_id_before
        # Avatar filled in from Google since it was empty before
        assert body["data"]["user"]["avatar_url"] == "https://example.com/pic.png"

        async with AsyncSessionLocal() as s:
            u = await s.get(User, user_id_before)
            assert u is not None
            assert u.google_sub == "cccc3333dddd4444"
            # Password still set (password login still works)
            assert u.password_hash is not None

    async def test_invalid_token_2001(self, client, google_client_id_set):
        """google-auth raises (bad signature / expired) → AUTH_INVALID_CREDENTIALS."""
        with patch(
            "google.oauth2.id_token.verify_oauth2_token",
            side_effect=ValueError("Token expired"),
        ):
            r = await client.post(
                "/api/v2/auth/google", json={"id_token": "tampered.jwt.token"}
            )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_wrong_audience_2001(self, client, google_client_id_set):
        """verify_oauth2_token returns idinfo with wrong aud → backend treats as invalid."""
        # The real google-auth lib raises on audience mismatch; mimic that.
        with patch(
            "google.oauth2.id_token.verify_oauth2_token",
            side_effect=ValueError("Wrong recipient"),
        ):
            r = await client.post(
                "/api/v2/auth/google", json={"id_token": "wrong.aud.jwt"}
            )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_not_configured_raises_server_error(self, client, monkeypatch):
        """If GOOGLE_CLIENT_ID env is empty, endpoint refuses (server misconfigured)."""
        from app.core.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "google_client_id", "")

        r = await client.post(
            "/api/v2/auth/google", json={"id_token": "any.jwt.token"}
        )
        # 500 / generic server error code
        assert r.status_code == 500
        assert r.json()["code"] != "1000"

    async def test_disabled_user_2005(self, client, google_client_id_set):
        """Once-registered user disabled later → google login refused."""
        idinfo = _make_idinfo(sub="eeee5555ffff6666", email="disabled@gmail.com")
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r1 = await client.post("/api/v2/auth/google", json={"id_token": "x"})
        assert r1.status_code == 200
        user_id = r1.json()["data"]["user"]["id"]

        async with AsyncSessionLocal() as s:
            u = await s.get(User, user_id)
            u.status = "disabled"
            await s.commit()

        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r2 = await client.post("/api/v2/auth/google", json={"id_token": "x"})
        assert r2.status_code == 403
        assert r2.json()["code"] == "2005"

    async def test_no_email_sub_only(self, client, google_client_id_set):
        """Edge case: id_token has no email (some Google scopes). Should still work."""
        idinfo = _make_idinfo(sub="ffff7777aaaa8888")  # no email, no name
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r = await client.post("/api/v2/auth/google", json={"id_token": "x"})
        assert r.status_code == 200
        body = r.json()
        # Username derived purely from google_sub
        assert body["data"]["user"]["username"].startswith("g_")
        assert body["data"]["user"]["email"] is None

    async def test_session_persisted(self, client, google_client_id_set):
        """Google login creates a UserSession row (refresh-token bookkeeping)."""
        idinfo = _make_idinfo(sub="9999aaaabbbb8888", email="sess@gmail.com")
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r = await client.post("/api/v2/auth/google", json={"id_token": "x"})
        assert r.status_code == 200
        refresh = r.json()["data"]["refresh_token"]

        from app.models.user_session import UserSession
        async with AsyncSessionLocal() as s:
            row = await s.scalar(
                select(UserSession).where(
                    UserSession.refresh_token_hash == hashlib.sha256(refresh.encode()).hexdigest()
                )
            )
            assert row is not None
            assert row.revoked_at is None

    async def test_audit_log_written(self, client, google_client_id_set):
        """user.google_auth audit row is written."""
        from app.models.audit_log import AuditLog
        idinfo = _make_idinfo(sub="audit1234abcd5678", email="audit@gmail.com")
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=idinfo):
            r = await client.post("/api/v2/auth/google", json={"id_token": "x"})
        assert r.status_code == 200

        from sqlalchemy import select, desc
        async with AsyncSessionLocal() as s:
            row = await s.scalar(
                select(AuditLog)
                .where(AuditLog.action == "user.google_auth")
                .order_by(desc(AuditLog.id))
                .limit(1)
            )
            assert row is not None
            assert row.actor_type == "user"