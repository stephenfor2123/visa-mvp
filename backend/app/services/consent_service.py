"""Consent records — GDPR Art.7 / Art.9 purpose-bound consent."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BizException, ErrorCode
from app.models.user import User
from app.models.user_consent import UserConsent

CONSENT_VERSION = "v1"

PURPOSE_SENSITIVE_UPLOAD = "sensitive_upload"
PURPOSE_PAYMENT = "payment"
PURPOSE_AI_LLM = "ai_llm"
PURPOSE_GOOGLE = "google"

SENSITIVE_PURPOSES = frozenset(
    {PURPOSE_SENSITIVE_UPLOAD, PURPOSE_AI_LLM}
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConsentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def has_active(
        self,
        user_id: int,
        purpose: str,
        *,
        version: str = CONSENT_VERSION,
    ) -> bool:
        row = await self.db.scalar(
            select(UserConsent).where(
                UserConsent.user_id == user_id,
                UserConsent.purpose == purpose,
                UserConsent.version == version,
                UserConsent.revoked_at.is_(None),
            )
        )
        return row is not None

    async def grant(
        self,
        user: User,
        purpose: str,
        *,
        version: str = CONSENT_VERSION,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserConsent:
        purpose = (purpose or "").strip().lower()
        if not purpose:
            raise BizException(ErrorCode.INVALID_PARAMS, message="purpose required")

        existing = await self.db.scalar(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.purpose == purpose,
                UserConsent.version == version,
            )
        )
        if existing is not None:
            existing.revoked_at = None
            existing.granted_at = _utcnow()
            existing.ip = ip
            existing.user_agent = (user_agent or "")[:512] or None
            await self.db.flush()
            return existing

        row = UserConsent(
            user_id=user.id,
            purpose=purpose,
            version=version,
            granted_at=_utcnow(),
            ip=ip,
            user_agent=(user_agent or "")[:512] or None,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def revoke(
        self,
        user: User,
        purpose: str,
        *,
        version: str = CONSENT_VERSION,
    ) -> bool:
        row = await self.db.scalar(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.purpose == purpose,
                UserConsent.version == version,
                UserConsent.revoked_at.is_(None),
            )
        )
        if row is None:
            return False
        row.revoked_at = _utcnow()
        await self.db.flush()
        return True

    async def list_for_user(self, user_id: int) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(UserConsent)
                .where(UserConsent.user_id == user_id)
                .order_by(UserConsent.granted_at.desc())
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "purpose": r.purpose,
                "version": r.version,
                "granted_at": r.granted_at.isoformat() if r.granted_at else None,
                "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
                "active": r.revoked_at is None,
            }
            for r in rows
        ]

    async def require_sensitive_processing(self, user: User) -> None:
        """Block OCR / upload / LLM when restricted or consent missing."""
        if getattr(user, "processing_restricted", False):
            raise BizException(
                ErrorCode.PROCESSING_RESTRICTED,
                message="Processing is restricted for this account",
            )
        ok = await self.has_active(user.id, PURPOSE_SENSITIVE_UPLOAD)
        if not ok:
            raise BizException(
                ErrorCode.CONSENT_REQUIRED,
                message="Consent required for sensitive material processing",
            )
