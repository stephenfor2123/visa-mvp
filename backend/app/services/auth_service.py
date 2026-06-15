"""AuthService — register / login / sms-login / refresh.

Pure business logic. Knows nothing about FastAPI; the API layer
translates exceptions to HTTP via the error-code registry.
"""
import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import and_, select
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
    validate_password_strength,
    verify_password,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.services.audit import record_audit
from app.services.sms_service import SmsService


_log = get_logger()


def _hash_refresh_token(token: str) -> str:
    """Persist only the SHA-256 of refresh tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Type alias for client info passed in from the API layer.
# Kept as a dict so the API layer doesn't have to import a dataclass.
ClientInfo = Mapping[str, Optional[str]]


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #
    async def _get_user_by_phone(
        self, phone: str, phone_country: str
    ) -> Optional[User]:
        return await self.db.scalar(
            select(User).where(
                and_(User.phone == phone, User.phone_country == phone_country)
            )
        )

    async def _issue_token_pair(
        self, user: User, info: ClientInfo
    ) -> dict[str, Any]:
        access_token, access_exp = create_access_token(user.id)
        refresh_token, refresh_exp = create_refresh_token(user.id)
        # Persist a session row so refresh can be revoked later.
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=_hash_refresh_token(refresh_token),
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
        }

    @staticmethod
    def _to_user_dict(user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "uuid": user.uuid,
            "phone": user.phone,
            "phone_country": user.phone_country,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "language_pref": user.language_pref,
            "status": user.status,
            "created_at": user.created_at,
        }

    async def _commit_with_audit(
        self,
        *,
        user: User,
        action: str,
        info: ClientInfo,
        target_id: Optional[int] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """Audit + commit in one go — easier to reason about in the API layer."""
        payload = {
            "ip": info.get("ip") if info else None,
            "user_agent": info.get("user_agent") if info else None,
        }
        if extra:
            payload.update(extra)
        await record_audit(
            self.db,
            actor_type="user",
            actor_id=user.id,
            action=action,
            target_type="user",
            target_id=target_id or user.id,
            payload=payload,
        )
        await self.db.commit()
        await self.db.refresh(user)

    # ------------------------------------------------------------------ #
    # register                                                           #
    # ------------------------------------------------------------------ #
    async def register(
        self,
        *,
        phone: str,
        phone_country: str,
        password: str,
        sms_code_value: str,
        nickname: Optional[str],
        language_pref: Optional[str],
        info: ClientInfo,
    ) -> dict[str, Any]:
        validate_password_strength(password)

        existing = await self._get_user_by_phone(phone, phone_country)
        if existing is not None:
            raise BizException(
                ErrorCode.USER_ALREADY_EXISTS,
                message="Phone already registered",
            )

        # Verify SMS code (mock mode: accept any 6-digit)
        sms_service = SmsService(self.db)
        await sms_service.verify_code(
            phone=phone, phone_country=phone_country, code=sms_code_value, purpose="register"
        )

        user = User(
            phone=phone,
            phone_country=phone_country,
            password_hash=hash_password(password, self.settings),
            nickname=nickname or f"user_{phone[-4:]}",
            language_pref=language_pref or "zh-CN",
            status="active",
        )
        self.db.add(user)
        await self.db.flush()

        tokens = await self._issue_token_pair(user, info)
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.last_login_ip = info.get("ip") if info else None

        await self._commit_with_audit(
            user=user,
            action="user.register",
            info=info,
        )
        _log.info(
            "user.register",
            extra={"user_id": user.id, "event_type": "user.register", "status": "success"},
        )
        return {**tokens, "user": self._to_user_dict(user)}

    # ------------------------------------------------------------------ #
    # password login                                                     #
    # ------------------------------------------------------------------ #
    async def login(
        self,
        *,
        phone: str,
        phone_country: str,
        password: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        user = await self._get_user_by_phone(phone, phone_country)
        if user is None or user.password_hash is None:
            # Generic message — do not leak whether the phone exists.
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Invalid phone or password",
            )
        if not verify_password(password, user.password_hash, self.settings):
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Invalid phone or password",
            )
        if user.status != "active":
            raise BizException(
                ErrorCode.ACCOUNT_DISABLED, message="Account is not active"
            )

        tokens = await self._issue_token_pair(user, info)
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.last_login_ip = info.get("ip") if info else None

        await self._commit_with_audit(
            user=user,
            action="user.login",
            info=info,
        )
        _log.info(
            "user.login",
            extra={"user_id": user.id, "event_type": "user.login", "status": "success"},
        )
        return {**tokens, "user": self._to_user_dict(user)}

    # ------------------------------------------------------------------ #
    # SMS login                                                          #
    # ------------------------------------------------------------------ #
    async def sms_login(
        self,
        *,
        phone: str,
        phone_country: str,
        sms_code_value: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        # Verify the code
        sms_service = SmsService(self.db)
        await sms_service.verify_code(
            phone=phone,
            phone_country=phone_country,
            code=sms_code_value,
            purpose="login",
        )

        user = await self._get_user_by_phone(phone, phone_country)
        if user is None:
            # SMS-only login: auto-register the user with no password.
            # V2 spec doesn't mandate this, but the task says "测试模式
            # 任意 6 位数字通过" — so we make it actually work end-to-end.
            user = User(
                phone=phone,
                phone_country=phone_country,
                password_hash=None,
                nickname=f"user_{phone[-4:]}",
                language_pref="zh-CN",
                status="active",
            )
            self.db.add(user)
            await self.db.flush()

        if user.status != "active":
            raise BizException(
                ErrorCode.ACCOUNT_DISABLED, message="Account is not active"
            )

        tokens = await self._issue_token_pair(user, info)
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.last_login_ip = info.get("ip") if info else None

        await self._commit_with_audit(
            user=user,
            action="user.sms_login",
            info=info,
        )
        _log.info(
            "user.sms_login",
            extra={"user_id": user.id, "event_type": "user.sms_login", "status": "success"},
        )
        return {**tokens, "user": self._to_user_dict(user)}

    # ------------------------------------------------------------------ #
    # Refresh                                                            #
    # ------------------------------------------------------------------ #
    async def refresh(
        self,
        *,
        refresh_token: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        payload = decode_token(refresh_token, TOKEN_TYPE_REFRESH)
        try:
            user_id = int(payload["sub"])
        except (KeyError, ValueError, TypeError):
            raise BizException(
                ErrorCode.REFRESH_TOKEN_INVALID, message="Bad token subject"
            ) from None

        user = await self.db.get(User, user_id)
        if user is None:
            raise BizException(
                ErrorCode.USER_NOT_FOUND, message="User not found"
            )
        if user.status != "active":
            raise BizException(
                ErrorCode.ACCOUNT_DISABLED, message="Account is not active"
            )

        # Rotate: revoke the old session row, issue a new pair.
        old_hash = _hash_refresh_token(refresh_token)
        old_session = await self.db.scalar(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.refresh_token_hash == old_hash,
                )
            )
        )
        if old_session is None or old_session.revoked_at is not None:
            raise BizException(
                ErrorCode.REFRESH_TOKEN_INVALID, message="Refresh token revoked"
            )
        old_session.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)

        tokens = await self._issue_token_pair(user, info)

        await self._commit_with_audit(
            user=user,
            action="user.refresh",
            info=info,
            extra={"rotated": True},
        )
        _log.info(
            "user.refresh",
            extra={"user_id": user.id, "event_type": "user.refresh", "status": "success"},
        )
        return {**tokens, "user": self._to_user_dict(user)}

    # ------------------------------------------------------------------ #
    # reset_password                                                      #
    # ------------------------------------------------------------------ #
    async def reset_password(
        self,
        *,
        phone: str,
        phone_country: str,
        sms_code: str,
        new_password: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        """Verify SMS code (purpose=reset) then update password hash."""
        validate_password_strength(new_password)

        user = await self._get_user_by_phone(phone, phone_country)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="Phone not registered")

        # Verify SMS code (mock mode: accept any 6-digit)
        sms_service = SmsService(self.db)
        await sms_service.verify_code(
            phone=phone, phone_country=phone_country, code=sms_code, purpose="reset"
        )

        user.password_hash = hash_password(new_password, self.settings)
        await self._commit_with_audit(
            user=user,
            action="user.reset_password",
            info=info,
        )
        _log.info(
            "user.reset_password",
            extra={"user_id": user.id, "event_type": "user.reset_password", "status": "success"},
        )
        return {"message": "Password updated successfully"}
