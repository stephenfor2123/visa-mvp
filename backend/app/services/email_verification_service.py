"""Email verification code service — generation, persistence, rate-limit + verify."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.models.email_code import EmailCode
from app.models.user import User
from app.services.email_service import VerificationCodeEmail, send_verification_code_email


_log = get_logger()

_OTP_SALT = "visa-mvp-email-otp-salt-v1"
_VALID_PURPOSES = frozenset({"register"})


def _hash_code(code: str) -> str:
    return hashlib.sha256(f"{_OTP_SALT}:{code}".encode("utf-8")).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class EmailVerificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def send_code(
        self, email: str, purpose: str, language_pref: str = "en"
    ) -> dict[str, Any]:
        email_clean = (email or "").strip().lower()
        purpose = (purpose or "").strip().lower()
        if purpose not in _VALID_PURPOSES:
            raise BizException(ErrorCode.INVALID_PARAMS, message="Invalid purpose")

        if purpose == "register":
            existing = await self.db.scalar(select(User).where(User.email == email_clean))
            if existing is not None:
                raise BizException(
                    ErrorCode.USER_ALREADY_EXISTS,
                    message="Email already registered",
                )

        await self._enforce_rate_limit(email_clean)

        code = _generate_code()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = now + timedelta(seconds=self.settings.email_code_ttl_seconds)

        row = EmailCode(
            email=email_clean,
            code_hash=_hash_code(code),
            purpose=purpose,
            expires_at=expires_at,
        )
        self.db.add(row)
        await self.db.flush()

        sent = send_verification_code_email(
            VerificationCodeEmail(
                to_email=email_clean,
                code=code,
                language_pref=language_pref or "en",
            ),
        )
        if not sent:
            raise BizException(
                ErrorCode.SERVER_ERROR,
                message="Failed to send verification email",
            )

        from app.services.audit import record_audit

        await record_audit(
            self.db,
            actor_type="system",
            action="email.send_code",
            target_type="email",
            target_id=None,
            payload={"email_hash": email_clean[:3] + "***", "purpose": purpose},
        )
        await self.db.commit()

        payload: dict[str, Any] = {
            "email": email_clean,
            "purpose": purpose,
            "language_pref": language_pref or "en",
            "expires_in": self.settings.email_code_ttl_seconds,
        }
        # Dev/test outbox mode echoes the code so frontend/E2E can autofill.
        if self.settings.email_backend == "outbox":
            payload["code"] = code
        return payload

    async def _enforce_rate_limit(self, email: str) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        latest = await self.db.scalar(
            select(EmailCode)
            .where(EmailCode.email == email)
            .order_by(EmailCode.created_at.desc())
            .limit(1)
        )
        if latest is not None and (now - latest.created_at).total_seconds() < self.settings.email_cooldown_seconds:
            raise BizException(
                ErrorCode.SMS_RATE_LIMIT,
                message=f"Code already sent — try again in {self.settings.email_cooldown_seconds}s",
            )

        one_day_ago = now - timedelta(days=1)
        daily_count = await self.db.scalar(
            select(func.count(EmailCode.id)).where(
                and_(EmailCode.email == email, EmailCode.created_at >= one_day_ago)
            )
        )
        if daily_count and daily_count >= self.settings.email_daily_limit:
            raise BizException(
                ErrorCode.SMS_RATE_LIMIT,
                message=f"Daily email limit reached ({self.settings.email_daily_limit}/day)",
            )

    async def verify_code(self, email: str, code: str, purpose: str) -> EmailCode:
        email_clean = (email or "").strip().lower()
        purpose = (purpose or "").strip().lower()

        if not (code.isdigit() and len(code) == 6):
            raise BizException(
                ErrorCode.SMS_CODE_INVALID,
                message="Verification code must be 6 digits",
            )

        if self.settings.email_backend == "outbox":
            class _MockRow:
                id = 0

            return _MockRow()  # type: ignore[return-value]

        code_hash = _hash_code(code)
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        row = await self.db.scalar(
            select(EmailCode)
            .where(
                and_(
                    EmailCode.email == email_clean,
                    EmailCode.purpose == purpose,
                    EmailCode.code_hash == code_hash,
                    EmailCode.used_at.is_(None),
                )
            )
            .order_by(EmailCode.created_at.desc())
            .limit(1)
        )
        if row is None:
            raise BizException(
                ErrorCode.SMS_CODE_INVALID,
                message="Invalid or already-used code",
            )
        if row.expires_at < now_naive:
            raise BizException(
                ErrorCode.SMS_CODE_EXPIRED,
                message="Code has expired",
            )
        return row

    async def mark_used(self, row: EmailCode) -> None:
        if getattr(row, "id", 0):
            db_row = await self.db.get(EmailCode, row.id)
            if db_row is not None:
                db_row.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
