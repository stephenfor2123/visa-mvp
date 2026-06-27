"""
/api/v2/auth/* — register, login, sms-login, refresh, send-code, reset-password.

W26 product change: register / login / reset-password now use
account (email or username) + password. SMS-based endpoints are kept
for legacy / admin tools but are no longer exposed in the user UI.

6 endpoints (V2 §4.1):
  - POST /api/v2/auth/register            (email + username + password)
  - POST /api/v2/auth/login               (account + password)
  - POST /api/v2/auth/sms-login           (legacy / admin)
  - POST /api/v2/auth/refresh
  - POST /api/v2/auth/send-code           (legacy / admin)
  - POST /api/v2/auth/reset-password      (account + new password, no SMS)
"""
import time
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import BizException
from app.core.logging import get_logger
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
    SmsLoginRequest,
    TokenPair,
)
from app.schemas.common import ApiResponse
from app.core.metrics import timed
from app.services.auth_service import AuthService
from app.services.sms_service import SmsService


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
    "/sms-login",
    response_model=ApiResponse[TokenPair],
    summary="SMS-code login (auto-registers on first use in mock mode)",
)
@timed
async def sms_login(
    body: SmsLoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    t0 = time.perf_counter()
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.sms_login(
        phone=body.phone,
        phone_country=body.phone_country,
        sms_code_value=body.sms_code,
        info=info,
    )
    _log.info(
        "user.sms_login",
        extra={
            "user_id": result["user"]["id"],
            "event_type": "user.sms_login",
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
    "/send-code",
    response_model=ApiResponse[dict],
    summary="Send SMS code (mock mode: returns raw code in response)",
)
@timed
async def send_code(
    body: SendCodeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    service = SmsService(db)
    payload = await service.send_code(
        phone=body.phone, phone_country=body.phone_country, purpose=body.purpose
    )
    return ApiResponse[dict](code="1000", message="OK", data=payload)


@router.post(
    "/reset-password",
    response_model=ApiResponse[dict],
    summary="Reset password by account (email or username) — W26 no SMS",
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
    await service.reset_password(
        account=body.account,
        new_password=body.new_password,
        info=info,
    )
    return ApiResponse[dict](code="1000", message="OK", data={"message": "Password updated successfully"})
