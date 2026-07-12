"""
/api/v2/auth/* — register, login, refresh, reset-password, Google/WeChat OAuth.

5 endpoints (V2 §4.1):
  - POST /api/v2/auth/register            (email + username + password + email_code)
  - POST /api/v2/auth/send-email-code     (send registration verification code)
  - POST /api/v2/auth/login               (account + password)
  - POST /api/v2/auth/refresh
  - POST /api/v2/auth/reset-password      (token from email + new password)
  - POST /api/v2/auth/google              (Google OAuth id_token)
  - POST /api/v2/auth/wechat              (WeChat miniprogram code)
"""
import time
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import BizException
from app.core.logging import get_logger
from app.schemas.auth import (
    GoogleAuthRequest,
    LoginRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendEmailCodeRequest,
    TokenPair,
    WechatAuthRequest,
)
from app.schemas.common import ApiResponse
from app.core.metrics import timed
from app.services.auth_service import AuthService
from app.services.email_verification_service import EmailVerificationService


router = APIRouter()
_log = get_logger()


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _client_info(
    request: Request,
    user_agent: Optional[str],
    device_fingerprint: Optional[str],
):
    return {
        "user_agent": user_agent or (request.headers.get("user-agent")),
        "ip": request.client.host if request.client else None,
        "device_fingerprint": device_fingerprint,
    }


# --------------------------------------------------------------------------- #
# 5 endpoints                                                                 #
# --------------------------------------------------------------------------- #
@router.post(
    "/register",
    response_model=ApiResponse[TokenPair],
    status_code=201,
    summary="Register a new user with email + username + password",
)
@timed
async def register(
    body: RegisterRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    t0 = time.perf_counter()
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.register(
        username=body.username,
        email=body.email,
        password=body.password,
        email_code=body.email_code,
        nickname=body.nickname,
        language_pref=body.language_pref,
        info=info,
    )
    _log.info(
        "user.register",
        extra={
            "user_id": result["user"]["id"],
            "event_type": "user.register",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "status": "success",
        },
    )
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/send-email-code",
    response_model=ApiResponse[dict],
    summary="Send email verification code (outbox mode: returns raw code in response)",
)
@timed
async def send_email_code(
    body: SendEmailCodeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    service = EmailVerificationService(db)
    payload = await service.send_code(
        email=body.email, purpose=body.purpose, language_pref=body.language_pref or "en"
    )
    return ApiResponse[dict](code="1000", message="OK", data=payload)


@router.post(
    "/login",
    response_model=ApiResponse[TokenPair],
    summary="Account (email or username) + password login",
)
@timed
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    t0 = time.perf_counter()
    service = AuthService(db)
    info = {
        "user_agent": user_agent or "",
        "device_fingerprint": x_device_fp or "",
    }
    try:
        result = await service.login(
            account=body.account,
            password=body.password,
            info=info,
        )
    except BizException as exc:
        _log.info(
            "user.login",
            extra={
                "user_id": None,
                "event_type": "user.login",
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                "status": "failed",
            },
        )
        raise
    _log.info(
        "user.login",
        extra={
            "user_id": result["user"]["id"],
            "event_type": "user.login",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "status": "success",
        },
    )
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenPair],
    summary="Rotate access + refresh tokens (V2 §4.1.4 sliding)",
)
@timed
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    t0 = time.perf_counter()
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.refresh(refresh_token=body.refresh_token, info=info)
    _log.info(
        "user.refresh",
        extra={
            "user_id": result["user"]["id"],
            "event_type": "user.refresh",
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "status": "success",
        },
    )
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/google",
    response_model=ApiResponse[TokenPair],
    summary="Google OAuth2 login — client sends id_token, backend verifies & issues JWT",
)
@timed
async def google_auth(
    body: GoogleAuthRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.google_auth(id_token_str=body.id_token, info=info)
    _log.info("user.google_auth", extra={"user_id": result["user"]["id"], "event_type": "user.google_auth", "status": "success"})
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/wechat",
    response_model=ApiResponse[TokenPair],
    summary="WeChat miniprogram login — client sends wx.login() code, backend exchanges for openid",
)
@timed
async def wechat_auth(
    body: WechatAuthRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
) -> ApiResponse[TokenPair]:
    service = AuthService(db)
    info = _client_info(request, user_agent, None)
    result = await service.wechat_auth(code=body.code, info=info)
    _log.info("user.wechat_auth", extra={"user_id": result["user"]["id"], "event_type": "user.wechat_auth", "status": "success"})
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/password-reset-request",
    response_model=ApiResponse[dict],
    summary="Request a password-reset link (sent to registered email)",
)
@timed
async def password_reset_request(
    body: PasswordResetRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[dict]:
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.request_password_reset(account=body.account, info=info)
    return ApiResponse[dict](code="1000", message="OK", data=result)


@router.post(
    "/reset-password",
    response_model=ApiResponse[dict],
    summary="Reset password using token from email link",
)
@timed
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[dict]:
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.reset_password(
        token=body.token,
        new_password=body.new_password,
        info=info,
    )
    return ApiResponse[dict](code="1000", message="OK", data=result)


@router.get(
    "/public-config",
    response_model=ApiResponse[dict],
    summary="Public privacy/support config (no auth)",
)
async def public_config() -> ApiResponse[dict]:
    settings = get_settings()
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={
            "privacy_support_email": settings.privacy_support_email,
        },
    )
