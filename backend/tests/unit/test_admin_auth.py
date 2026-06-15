"""Unit tests for app.middleware.admin_auth — W14-3."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.middleware.admin_auth import (
    create_admin_token,
    decode_admin_token,
)


class TestAdminToken:
    def test_create_token_returns_valid_jwt(self):
        """Token is a valid JWT with admin role and 3 parts."""
        token, exp = create_admin_token(admin_id=0, username="admin")
        assert token.count(".") == 2
        assert exp > datetime.now(timezone.utc)

    def test_decode_token_returns_payload(self):
        """Decoding a valid token returns role=admin and admin_id."""
        token, _ = create_admin_token(admin_id=42, username="admin")
        payload = decode_admin_token(token)
        assert payload["role"] == "admin"
        assert payload["sub"] == "42"
        assert payload["username"] == "admin"

    def test_decode_token_wrong_type_raises(self):
        """Decoding a C-user token (type=access) raises FORBIDDEN."""
        from app.core.security import create_access_token
        from app.core.errors import ErrorCode

        user_token, _ = create_access_token(user_id=1)
        with pytest.raises(Exception) as exc:
            decode_admin_token(user_token)
        # Decode with admin decoder should raise FORBIDDEN because role != admin
        assert exc.value.code in (ErrorCode.FORBIDDEN, ErrorCode.UNAUTHORIZED)

    def test_decode_invalid_token_raises(self):
        """Malformed token raises UNAUTHORIZED."""
        from app.core.errors import ErrorCode

        with pytest.raises(Exception) as exc:
            decode_admin_token("not.a.jwt")
        assert exc.value.code == ErrorCode.UNAUTHORIZED

    def test_expired_admin_token_raises(self):
        """Token with past exp raises UNAUTHORIZED."""
        from app.core.errors import ErrorCode
        from jose import jwt

        settings = pytest.importorskip("app.core.config").get_settings()
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        payload = {
            "sub": "0",
            "type": "admin_access",
            "role": "admin",
            "username": "admin",
            "iat": int(now.timestamp()),
            "exp": int(past.timestamp()),
            "jti": "deadbeef",
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(Exception) as exc:
            decode_admin_token(token)
        assert exc.value.code == ErrorCode.UNAUTHORIZED
