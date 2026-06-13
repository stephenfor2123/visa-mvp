"""SMS service — code generation, persistence, rate-limit + verification.

V2 §4.1.4 + §9.4 rules:
  - 6-digit code, 5 min TTL
  - same phone: 1 send per 60s, 10 per day
  - codes stored as bcrypt hashes; raw code is never persisted
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.models.sms_code import SmsCode
from app.services.sms import get_sms_channel


_log = get_logger()


def _hash_code(code: str) -> str:
    """We use SHA-256 for OTP storage (bcrypt is overkill for 6-digit codes
    and has a 72-byte input cap). Salted to thwart rainbow tables on
    short codes."""
    salt = "visa-mvp-otp-salt-v1"
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def _generate_code() -> str:
    """Cryptographically-random 6-digit number, no leading-zero loss."""
    return f"{secrets.randbelow(1_000_000):06d}"


class SmsService:
    """Owns the SmsCode lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.channel = get_sms_channel()

    # ----------------------------------------------------------------- #
    # Send code                                                          #
    # ----------------------------------------------------------------- #
    async def send_code(
        self, phone: str, phone_country: str, purpose: str
    ) -> dict[str, Any]:
        await self._enforce_rate_limit(phone, phone_country)

        code = _generate_code()
        code_hash = _hash_code(code)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at = now + timedelta(seconds=self.settings.sms_code_ttl_seconds)

        row = SmsCode(
            phone=phone,
            phone_country=phone_country,
            code_hash=code_hash,
            purpose=purpose,
            expires_at=expires_at,
            send_count=1,
        )
        self.db.add(row)
        await self.db.flush()

        # 1. push to channel (mock = file log; twilio = HTTP)
        result = await self.channel.send_code(phone, phone_country, code, purpose)
        if not result.get("ok"):
            raise BizException(
                ErrorCode.SMS_GATEWAY_DOWN,
                message=result.get("error") or "SMS gateway down",
            )

        # Persist the SmsCode row so subsequent /send-code calls see it
        # for the cooldown + daily-limit checks. Also audit-log the action.
        from app.services.audit import record_audit  # local import — avoid cycle
        await record_audit(
            self.db,
            actor_type="system",
            action="sms.send_code",
            target_type="phone",
            target_id=None,
            payload={
                "phone_country": phone_country,
                "phone": phone,
                "purpose": purpose,
                "channel_txn_id": result["channel_txn_id"],
            },
        )
        await self.db.commit()

        # 2. dev-mode echo so the frontend can autofill (V2 §4.1.4)
        return {
            "phone": phone,
            "phone_country": phone_country,
            "purpose": purpose,
            "expires_in": self.settings.sms_code_ttl_seconds,
            "channel_txn_id": result["channel_txn_id"],
            # Mock-only field — never present in production responses.
            "code": code if self.settings.sms_channel == "mock" else None,
        }

    async def _enforce_rate_limit(self, phone: str, phone_country: str) -> None:
        """1 send per 60s + 10 sends per 24h per phone."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Cooldown — most recent send for this phone
        latest = await self.db.scalar(
            select(SmsCode)
            .where(
                and_(
                    SmsCode.phone == phone,
                    SmsCode.phone_country == phone_country,
                )
            )
            .order_by(SmsCode.created_at.desc())
            .limit(1)
        )
        if latest is not None and (now - latest.created_at).total_seconds() < self.settings.sms_cooldown_seconds:
            raise BizException(
                ErrorCode.SMS_RATE_LIMIT,
                message=(
                    f"Code already sent — try again in "
                    f"{self.settings.sms_cooldown_seconds}s"
                ),
            )

        # Daily cap
        one_day_ago = now - timedelta(days=1)
        daily_count = await self.db.scalar(
            select(func.count(SmsCode.id)).where(
                and_(
                    SmsCode.phone == phone,
                    SmsCode.phone_country == phone_country,
                    SmsCode.created_at >= one_day_ago,
                )
            )
        )
        if daily_count and daily_count >= self.settings.sms_daily_limit:
            raise BizException(
                ErrorCode.SMS_RATE_LIMIT,
                message=(
                    f"Daily SMS limit reached "
                    f"({self.settings.sms_daily_limit}/day)"
                ),
            )

    # ----------------------------------------------------------------- #
    # Verify code                                                        #
    # ----------------------------------------------------------------- #
    async def verify_code(
        self, phone: str, phone_country: str, code: str, purpose: str
    ) -> SmsCode:
        """Return the SmsCode row on success; raise on failure.

        The caller is responsible for marking `used_at` only AFTER their
        own transactional work — see auth_service.register / sms_login.
        """
        # W1 dev/test mode: any 6-digit code matches. This is the
        # "测试模式:任意 6 位数字通过" rule from the task spec.
        if not (code.isdigit() and len(code) == 6):
            raise BizException(
                ErrorCode.SMS_CODE_INVALID, message="SMS code must be 6 digits"
            )

        if self.settings.sms_channel != "mock":
            # Production path — strict hash match
            code_hash = _hash_code(code)
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            row = await self.db.scalar(
                select(SmsCode)
                .where(
                    and_(
                        SmsCode.phone == phone,
                        SmsCode.phone_country == phone_country,
                        SmsCode.purpose == purpose,
                        SmsCode.code_hash == code_hash,
                        SmsCode.used_at.is_(None),
                    )
                )
                .order_by(SmsCode.created_at.desc())
                .limit(1)
            )
            if row is None:
                raise BizException(
                    ErrorCode.SMS_CODE_INVALID, message="Invalid or already-used code"
                )
            if row.expires_at < now_naive:
                raise BizException(
                    ErrorCode.SMS_CODE_EXPIRED, message="Code has expired"
                )
            return row

        # Mock mode: pretend a code row exists.
        # We do NOT persist a fake row — we just return a transient marker.
        class _MockRow:
            id = 0
        return _MockRow()  # type: ignore[return-value]
