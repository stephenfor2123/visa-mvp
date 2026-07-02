"""AuthService — register / login / reset-password / refresh / OAuth."""
import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import and_, or_, select
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


_log = get_logger()


def _hash_refresh_token(token: str) -> str:
    """Persist only the SHA-256 of refresh tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Type alias for client info passed in from the API layer.
# Kept as a dict so the API layer doesn't have to import a dataclass.
ClientInfo = Mapping[str, Optional[str]]

# Detect "looks-like-email" so we can branch on email vs username in _get_user_by_account.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #
    async def _get_user_by_account(self, account: str) -> Optional[User]:
        """Lookup by either email (case-insensitive) or username."""
        account = (account or "").strip()
        if not account:
            return None
        if _EMAIL_RE.match(account):
            return await self.db.scalar(
                select(User).where(User.email == account.lower())
            )
        return await self.db.scalar(
            select(User).where(User.username == account)
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
            "username": user.username,
            "email": user.email,
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
    # register (W26: email + username + password)                        #
    # ------------------------------------------------------------------ #
    async def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        nickname: Optional[str],
        language_pref: Optional[str],
        info: ClientInfo,
    ) -> dict[str, Any]:
        validate_password_strength(password)

        username_clean = username.strip()
        email_clean = email.strip().lower()

        # Uniqueness: email + username
        existing_email = await self.db.scalar(
            select(User).where(User.email == email_clean)
        )
        if existing_email is not None:
            raise BizException(
                ErrorCode.USER_ALREADY_EXISTS,
                message="Email already registered",
            )
        existing_username = await self.db.scalar(
            select(User).where(User.username == username_clean)
        )
        if existing_username is not None:
            raise BizException(
                ErrorCode.USER_ALREADY_EXISTS,
                message="Username already taken",
            )

        user = User(
            username=username_clean,
            email=email_clean,
            password_hash=hash_password(password, self.settings),
            nickname=nickname or f"user_{username_clean[-4:]}",
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
    # password login (W26: account = email OR username)                  #
    # ------------------------------------------------------------------ #
    async def login(
        self,
        *,
        account: str,
        password: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        user = await self._get_user_by_account(account)
        if user is None or user.password_hash is None:
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Invalid account or password",
            )
        if not verify_password(password, user.password_hash, self.settings):
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Invalid account or password",
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
    # Google OAuth login / auto-register                                 #
    # ------------------------------------------------------------------ #
    async def google_auth(self, id_token_str: str, info: ClientInfo) -> dict[str, Any]:
        """Verify Google ID token and issue JWT pair. Auto-registers on first use."""
        if not self.settings.google_client_id:
            raise BizException(ErrorCode.SERVER_ERROR, message="Google login not configured")

        try:
            from google.oauth2 import id_token as _gid
            from google.auth.transport.requests import Request as _GReq
            idinfo = _gid.verify_oauth2_token(id_token_str, _GReq(), self.settings.google_client_id)
        except Exception as exc:
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS, message="Invalid Google token"
            ) from exc

        google_sub: str = idinfo["sub"]
        email: str = (idinfo.get("email") or "").lower().strip()
        name: str = idinfo.get("name", "")
        avatar: str = idinfo.get("picture", "")

        user: Optional[User] = await self.db.scalar(
            select(User).where(User.google_sub == google_sub)
        )
        if user is None and email:
            user = await self.db.scalar(select(User).where(User.email == email))

        if user is None:
            base_username = f"g_{google_sub[-8:]}"
            username = base_username
            if await self.db.scalar(select(User).where(User.username == username)) is not None:
                username = f"g_{google_sub[-12:]}"
            user = User(
                google_sub=google_sub,
                email=email or None,
                username=username,
                password_hash=None,
                nickname=name or username,
                avatar_url=avatar or None,
                language_pref="zh-CN",
                status="active",
            )
            self.db.add(user)
            await self.db.flush()
        else:
            if not user.google_sub:
                user.google_sub = google_sub
            if avatar and not user.avatar_url:
                user.avatar_url = avatar

        if user.status != "active":
            raise BizException(ErrorCode.ACCOUNT_DISABLED, message="Account is not active")

        tokens = await self._issue_token_pair(user, info)
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.last_login_ip = info.get("ip") if info else None
        await self._commit_with_audit(user=user, action="user.google_auth", info=info)
        _log.info("user.google_auth", extra={"user_id": user.id, "event_type": "user.google_auth", "status": "success"})
        return {**tokens, "user": self._to_user_dict(user)}

    # ------------------------------------------------------------------ #
    # WeChat miniprogram login / auto-register                           #
    # ------------------------------------------------------------------ #
    async def wechat_auth(self, code: str, info: ClientInfo) -> dict[str, Any]:
        """Exchange wx.login() code for openid, issue JWT pair. Auto-registers on first use."""
        if not self.settings.wechat_appid or not self.settings.wechat_appsecret:
            raise BizException(ErrorCode.SERVER_ERROR, message="WeChat login not configured")

        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": self.settings.wechat_appid,
                    "secret": self.settings.wechat_appsecret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
        data: dict = resp.json()
        if data.get("errcode") and data["errcode"] != 0:
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS,
                message=f"WeChat auth failed: {data.get('errmsg', 'unknown')}",
            )

        openid: str = data.get("openid", "")
        if not openid:
            raise BizException(ErrorCode.AUTH_INVALID_CREDENTIALS, message="WeChat openid missing")

        user: Optional[User] = await self.db.scalar(
            select(User).where(User.wechat_openid == openid)
        )
        if user is None:
            suffix = openid[-8:]
            username = f"wx_{suffix}"
            if await self.db.scalar(select(User).where(User.username == username)) is not None:
                username = f"wx_{openid[-12:]}"
            user = User(
                wechat_openid=openid,
                email=f"wx_{suffix}@htex.local",
                username=username,
                password_hash=None,
                nickname=f"微信用户_{suffix}",
                language_pref="zh-CN",
                status="active",
            )
            self.db.add(user)
            await self.db.flush()

        if user.status != "active":
            raise BizException(ErrorCode.ACCOUNT_DISABLED, message="Account is not active")

        tokens = await self._issue_token_pair(user, info)
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.last_login_ip = info.get("ip") if info else None
        await self._commit_with_audit(user=user, action="user.wechat_auth", info=info)
        _log.info("user.wechat_auth", extra={"user_id": user.id, "event_type": "user.wechat_auth", "status": "success"})
        return {**tokens, "user": self._to_user_dict(user)}

    # ------------------------------------------------------------------ #
    # reset_password (W26: by account, no SMS code)                       #
    # ------------------------------------------------------------------ #
    async def reset_password(
        self,
        *,
        account: str,
        new_password: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        """Reset by account (email or username). Caller (e.g. admin) is
        responsible for verifying the user owns the account (e.g. via
        a separately-issued email token, or admin override)."""
        validate_password_strength(new_password)

        user = await self._get_user_by_account(account)
        if user is None:
            raise BizException(ErrorCode.USER_NOT_FOUND, message="Account not registered")

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
