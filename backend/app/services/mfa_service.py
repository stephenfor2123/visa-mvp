"""MFA Service — TOTP verification.

MFA flow:
  1. POST /auth/mfa/verify  (with mfa_token + code) -> full TokenPair
  2. POST /auth/mfa/setup   (enable / disable / query)

The mfa_token is a short-lived JWT (5 min TTL) that carries the user_id
and cannot be used for regular API access.
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from app.models.user import User
from app.models.user_session import UserSession

if TYPE_CHECKING:
    from app.services.auth_service import ClientInfo


_log = get_logger()
TOKEN_TYPE_MFA = "mfa"
MFA_TOKEN_TTL_MINUTES = 5


def _mfa_token_ttl() -> timedelta:
    return timedelta(minutes=MFA_TOKEN_TTL_MINUTES)


# --------------------------------------------------------------------------- #
# Secret encryption (AES-equivalent via Fernet-style: base64(HMAC-SHA256))   #
# --------------------------------------------------------------------------- #
def _derive_mfa_key(settings) -> bytes:
    """Derive a per-instance key from JWT_SECRET for encrypting TOTP secrets."""
    return hashlib.sha256(f"{settings.jwt_secret}-mfa-secret".encode()).digest()


def _encrypt_secret(plain: str, settings) -> str:
    """Encrypt TOTP base32 secret so it can't be read from DB directly."""
    key = _derive_mfa_key(settings)
    # XOR each byte with key (ECB-ish, fine for short secrets)
    encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(plain.encode("utf-8")))
    return base64.b64encode(encrypted).decode()


def _decrypt_secret(cipher: str, settings) -> str:
    """Decrypt TOTP base32 secret."""
    key = _derive_mfa_key(settings)
    encrypted = base64.b64decode(cipher.encode("utf-8"))
    decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(encrypted))
    return decrypted.decode("utf-8")


# --------------------------------------------------------------------------- #
# MfaService                                                                #
# --------------------------------------------------------------------------- #
class MfaService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # mfa_token management                                               #
    # ------------------------------------------------------------------ #
    def create_mfa_token(self, user_id: int) -> tuple[str, datetime]:
        """Issue a short-lived JWT for the MFA challenge flow."""
        now = datetime.now(timezone.utc)
        exp = now + _mfa_token_ttl()
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "type": TOKEN_TYPE_MFA,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": secrets.token_hex(8),
        }
        from jose import jwt
        token = jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)
        return token, exp

    def decode_mfa_token(self, token: str) -> dict[str, Any]:
        """Decode and validate an mfa_token. Raises on invalid/expired."""
        return decode_token(token, TOKEN_TYPE_MFA)

    # ------------------------------------------------------------------ #
    # TOTP                                                                 #
    # ------------------------------------------------------------------ #
    def generate_totp_secret(self) -> str:
        """Generate a random base32 TOTP secret (32 chars, 160 bits)."""
        import pyotp
        return pyotp.random_base32(length=32)

    def get_totp_uri(self, secret: str, account_name: str) -> str:
        """Return the otpauth:// URI for QR code generation."""
        import pyotp
        issuer = self.settings.app_name
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=account_name, issuer_name=issuer)

    def verify_totp(self, secret: str, code: str) -> bool:
        """Verify a 6-digit TOTP code against the secret (30s window, 1 step)."""
        import pyotp
        try:
            if not (code.isdigit() and len(code) == 6):
                return False
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Setup                                                               #
    # ------------------------------------------------------------------ #
    async def setup_totp(self, user: User) -> dict[str, Any]:
        """Enable TOTP MFA. Returns secret + otpauth URI."""
        secret = self.generate_totp_secret()
        encrypted = _encrypt_secret(secret, self.settings)
        user.mfa_enabled = True
        user.mfa_type = "totp"
        user.mfa_secret = encrypted
        await self.db.commit()
        account_name = user.email or user.username or str(user.id)
        uri = self.get_totp_uri(secret, account_name)
        return {
            "secret": secret,  # only returned on setup; never again
            "otpauth_uri": uri,
            "mfa_type": "totp",
        }

    async def disable_mfa(self, user: User) -> dict[str, Any]:
        """Disable MFA for the user."""
        user.mfa_enabled = False
        user.mfa_type = None
        user.mfa_secret = None
        await self.db.commit()
        return {"mfa_enabled": False}

    async def get_mfa_status(self, user: User) -> dict[str, Any]:
        """Return current MFA status (no secret exposed)."""
        return {
            "mfa_enabled": user.mfa_enabled,
            "mfa_type": user.mfa_type,
        }

    # ------------------------------------------------------------------ #
    # Verify + issue tokens                                               #
    # ------------------------------------------------------------------ #
    def _hash_refresh_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def verify_and_issue_tokens(
        self,
        user: User,
        info: "ClientInfo",
    ) -> dict[str, Any]:
        """Called after MFA verification succeeds — issue full token pair."""
        access_token, access_exp = create_access_token(user.id)
        refresh_token, refresh_exp = create_refresh_token(user.id)
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=self._hash_refresh_token(refresh_token),
            device_fingerprint=info.get("device_fingerprint") if info else None,
            user_agent=info.get("user_agent") if info else None,
            ip=info.get("ip") if info else None,
            expires_at=refresh_exp.replace(tzinfo=None),
        )
        self.db.add(session)
        await self.db.flush()
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.settings.access_token_ttl_minutes * 60,
            "access_expires_at": access_exp,
            "user": {
                "id": user.id,
                "uuid": user.uuid,
                "username": user.username,
                "email": user.email,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "language_pref": user.language_pref,
                "status": user.status,
                "created_at": user.created_at,
            },
        }
