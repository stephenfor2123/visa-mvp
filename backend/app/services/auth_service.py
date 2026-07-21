"""AuthService — register / login / reset-password / refresh / OAuth."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from jose import JWTError, jwt
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    assert_token_valid_for_user,
    bump_password_changed_at,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    invalidate_user_sessions,
    validate_password_strength,
    verify_password,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.services.audit import record_audit
from app.services.email_service import (
    PasswordChangedEmail,
    PasswordResetEmail,
    WelcomeEmail,
    send_password_changed_email,
    send_password_reset_email,
    send_welcome_email,
)
from app.services.email_verification_service import EmailVerificationService


_log = get_logger()


def _hash_refresh_token(token: str) -> str:
    """Persist only the SHA-256 of refresh tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Type alias for client info passed in from the API layer.
# Kept as a dict so the API layer doesn't have to import a dataclass.
ClientInfo = Mapping[str, Optional[str]]

# Detect "looks-like-email" so we can branch on email vs username in _get_user_by_account.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_PASSWORD_RESET_TOKEN_TYPE = "password_reset"
_PASSWORD_RESET_TTL_MINUTES = 30


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
        email_code: str,
        nickname: Optional[str],
        language_pref: Optional[str],
        info: ClientInfo,
        age_confirmed_16: bool = False,
    ) -> dict[str, Any]:
        validate_password_strength(password)
        if not age_confirmed_16:
            raise BizException(
                ErrorCode.AGE_CONFIRMATION_REQUIRED,
                message="You must confirm you are at least 16 years old",
            )

        username_clean = username.strip()
        email_clean = email.strip().lower()

        # Verify email OTP before creating the account.
        email_svc = EmailVerificationService(self.db)
        code_row = await email_svc.verify_code(email_clean, email_code, "register")
        await email_svc.mark_used(code_row)

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

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        user = User(
            username=username_clean,
            email=email_clean,
            password_hash=hash_password(password, self.settings),
            nickname=nickname or f"user_{username_clean[-4:]}",
            language_pref=language_pref or "zh-CN",
            status="active",
            age_confirmed_16_at=now,
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

        # W48: best-effort welcome email. Never let it bubble back into the
        # API response — failures are logged inside the service.
        send_welcome_email(
            WelcomeEmail(
                to_email=user.email,
                nickname=user.nickname or user.username,
                username=user.username,
                language_pref=user.language_pref or "zh-CN",
            )
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
        assert_token_valid_for_user(payload, user)

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
    async def google_auth(
        self,
        id_token_str: str,
        info: ClientInfo,
        *,
        age_confirmed_16: bool = False,
    ) -> dict[str, Any]:
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
            if not age_confirmed_16:
                raise BizException(
                    ErrorCode.AGE_CONFIRMATION_REQUIRED,
                    message="You must confirm you are at least 16 years old",
                )
            base_username = f"g_{google_sub[-8:]}"
            username = base_username
            if await self.db.scalar(select(User).where(User.username == username)) is not None:
                username = f"g_{google_sub[-12:]}"
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            user = User(
                google_sub=google_sub,
                email=email or None,
                username=username,
                password_hash=None,
                nickname=name or username,
                avatar_url=avatar or None,
                language_pref="zh-CN",
                status="active",
                age_confirmed_16_at=now,
            )
            self.db.add(user)
            await self.db.flush()
        else:
            if not user.google_sub:
                user.google_sub = google_sub
            if avatar and not user.avatar_url:
                user.avatar_url = avatar
            if not user.age_confirmed_16_at:
                if not age_confirmed_16:
                    raise BizException(
                        ErrorCode.AGE_CONFIRMATION_REQUIRED,
                        message="You must confirm you are at least 16 years old",
                    )
                user.age_confirmed_16_at = datetime.now(timezone.utc).replace(tzinfo=None)

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
    async def wechat_auth(
        self,
        code: str,
        info: ClientInfo,
        *,
        age_confirmed_16: bool = False,
    ) -> dict[str, Any]:
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
            if not age_confirmed_16:
                raise BizException(
                    ErrorCode.AGE_CONFIRMATION_REQUIRED,
                    message="You must confirm you are at least 16 years old",
                )
            suffix = openid[-8:]
            username = f"wx_{suffix}"
            if await self.db.scalar(select(User).where(User.username == username)) is not None:
                username = f"wx_{openid[-12:]}"
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            user = User(
                wechat_openid=openid,
                email=f"wx_{suffix}@htex.local",
                username=username,
                password_hash=None,
                nickname=f"微信用户_{suffix}",
                language_pref="zh-CN",
                status="active",
                age_confirmed_16_at=now,
            )
            self.db.add(user)
            await self.db.flush()
        else:
            if age_confirmed_16 and not user.age_confirmed_16_at:
                user.age_confirmed_16_at = datetime.now(timezone.utc).replace(tzinfo=None)

        if user.status != "active":
            raise BizException(ErrorCode.ACCOUNT_DISABLED, message="Account is not active")

        tokens = await self._issue_token_pair(user, info)
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        user.last_login_ip = info.get("ip") if info else None
        await self._commit_with_audit(user=user, action="user.wechat_auth", info=info)
        _log.info("user.wechat_auth", extra={"user_id": user.id, "event_type": "user.wechat_auth", "status": "success"})
        return {**tokens, "user": self._to_user_dict(user)}

    # ------------------------------------------------------------------ #
    # Password reset (email token — no unauthenticated account+password)   #
    # ------------------------------------------------------------------ #
    def _make_password_reset_token(self, user_id: int) -> str:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=_PASSWORD_RESET_TTL_MINUTES)
        payload = {
            "sub": str(user_id),
            "type": _PASSWORD_RESET_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": secrets.token_hex(8),
        }
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)

    def _decode_password_reset_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
            )
        except JWTError:
            raise BizException(
                ErrorCode.PASSWORD_RESET_TOKEN_INVALID, message="Invalid or expired reset link"
            ) from None

        if payload.get("type") != _PASSWORD_RESET_TOKEN_TYPE:
            raise BizException(
                ErrorCode.PASSWORD_RESET_TOKEN_INVALID, message="Invalid reset link"
            )
        exp = payload.get("exp")
        if exp is not None and datetime.fromtimestamp(int(exp), tz=timezone.utc) < datetime.now(timezone.utc):
            raise BizException(
                ErrorCode.PASSWORD_RESET_TOKEN_EXPIRED, message="Reset link has expired"
            )
        return payload

    def _frontend_base(self) -> str:
        return self.settings.app_frontend_base or "http://localhost:5173"

    async def request_password_reset(
        self,
        *,
        account: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        """Always returns a generic success message (no account enumeration)."""
        user = await self._get_user_by_account(account)
        if user is not None and user.email:
            token = self._make_password_reset_token(user.id)
            reset_url = f"{self._frontend_base()}/forgot-password?token={token}"
            send_password_reset_email(
                PasswordResetEmail(
                    to_email=user.email,
                    nickname=user.nickname or user.username or "there",
                    language_pref=user.language_pref or "en",
                    reset_url=reset_url,
                ),
            )
            _log.info(
                "user.password_reset.requested",
                extra={
                    "user_id": user.id,
                    "event_type": "user.password_reset.requested",
                    "status": "sent",
                },
            )
        else:
            _log.info(
                "user.password_reset.requested",
                extra={
                    "event_type": "user.password_reset.requested",
                    "status": "noop",
                    "account_hint": account[:3] + "***" if account else None,
                },
            )
        return {"message": "If the account exists, a reset link has been sent to the registered email"}

    async def reset_password(
        self,
        *,
        token: str,
        new_password: str,
        info: ClientInfo,
    ) -> dict[str, Any]:
        """Reset password using a token from the reset email."""
        payload = self._decode_password_reset_token(token)
        user_id = int(payload.get("sub") or 0)
        if user_id <= 0:
            raise BizException(
                ErrorCode.PASSWORD_RESET_TOKEN_INVALID, message="Invalid reset link"
            )

        user = await self.db.get(User, user_id)
        if user is None or user.status in {"destroyed", "disabled"}:
            raise BizException(
                ErrorCode.PASSWORD_RESET_TOKEN_INVALID, message="Invalid reset link"
            )

        validate_password_strength(new_password)
        user.password_hash = hash_password(new_password, self.settings)
        bump_password_changed_at(user)
        await invalidate_user_sessions(self.db, user.id)
        await self._commit_with_audit(
            user=user,
            action="user.reset_password",
            info=info,
        )
        login_url = f"{self._frontend_base()}/login"
        if user.email:
            send_password_changed_email(
                PasswordChangedEmail(
                    to_email=user.email,
                    nickname=user.nickname or user.username or "there",
                    language_pref=user.language_pref or "en",
                    login_url=login_url,
                ),
            )
        _log.info(
            "user.reset_password",
            extra={"user_id": user.id, "event_type": "user.reset_password", "status": "success"},
        )
        return {"message": "Password updated successfully"}
