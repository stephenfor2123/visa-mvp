"""
/api/v2/auth/* — register, login, sms-login, refresh, send-code.

5 endpoints (V2 §4.1):
  - POST /api/v2/auth/register
  - POST /api/v2/auth/login
  - POST /api/v2/auth/sms-login
  - POST /api/v2/auth/refresh
  - POST /api/v2/auth/send-code
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    SendCodeRequest,
    SmsLoginRequest,
    TokenPair,
)
from app.schemas.common import ApiResponse
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
    summary="Register a new user with phone + SMS code + password",
)
async def register(
    body: RegisterRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.register(
        phone=body.phone,
        phone_country=body.phone_country,
        password=body.password,
        sms_code_value=body.sms_code,
        nickname=body.nickname,
        language_pref=body.language_pref,
        info=info,
    )
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/login",
    response_model=ApiResponse[TokenPair],
    summary="Phone + password login",
)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.login(
        phone=body.phone,
        phone_country=body.phone_country,
        password=body.password,
        info=info,
    )
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/sms-login",
    response_model=ApiResponse[TokenPair],
    summary="SMS-code login (auto-registers on first use in mock mode)",
)
async def sms_login(
    body: SmsLoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.sms_login(
        phone=body.phone,
        phone_country=body.phone_country,
        sms_code_value=body.sms_code,
        info=info,
    )
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenPair],
    summary="Rotate access + refresh tokens (V2 §4.1.4 sliding)",
)
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_agent: Annotated[Optional[str], Header(alias="User-Agent")] = None,
    x_device_fp: Annotated[Optional[str], Header(alias="X-Device-Fingerprint")] = None,
) -> ApiResponse[TokenPair]:
    service = AuthService(db)
    info = _client_info(request, user_agent, x_device_fp)
    result = await service.refresh(refresh_token=body.refresh_token, info=info)
    return ApiResponse[TokenPair](code="1000", message="OK", data=TokenPair(**result))


@router.post(
    "/send-code",
    response_model=ApiResponse[dict],
    summary="Send SMS code (mock mode: returns raw code in response)",
)
async def send_code(
    body: SendCodeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    service = SmsService(db)
    payload = await service.send_code(
        phone=body.phone, phone_country=body.phone_country, purpose=body.purpose
    )
    return ApiResponse[dict](code="1000", message="OK", data=payload)
