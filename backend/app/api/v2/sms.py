"""/api/v2/sms/* — B-W6-1 standalone SMS endpoints (V2 §6.1, Mock-only).

Endpoints (4):
  - POST /api/v2/sms/send          — generate + store OTP, echo code in mock
  - POST /api/v2/sms/verify        — verify OTP, mint JWT (mock: always issues)
  - GET  /api/v2/sms/{message_id}  — query send status (mock: sent/unknown)
  - POST /api/v2/sms/template      — register a template (in-memory)

Why a standalone set when /api/v2/auth/send-code already exists?
  /auth/send-code is tightly coupled to the SmsService DB flow (cooldown
  + daily limit + audit log) and is consumed by the register/login
  flows. The W6-1 standalone set is for the front-end dev console and
  for V2.1 — when we wire Tencent Cloud, the swap lives in
  `services/sms_provider.py` and these 4 endpoints are the public
  contract.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path

from app.core.config import get_settings
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import create_access_token
from app.schemas.common import ApiResponse
from app.schemas.sms import (
    MessageStatusData,
    RegisterTemplateRequest,
    SendCodeData,
    SendCodeRequest,
    TemplateData,
    VerifyCodeData,
    VerifyCodeRequest,
)
from app.services.sms_provider import (
    CodeExpired,
    CodeMismatch,
    MockSmsProvider,
    NoCodeOnFile,
    get_sms_provider,
)


router = APIRouter()
_log = get_logger()


def _provider() -> MockSmsProvider:
    """Type-narrow the singleton to MockSmsProvider for the /template + /status
    helpers — those are mock-only in V2."""
    p = get_sms_provider()
    if not isinstance(p, MockSmsProvider):
        # V2.1 path — only the 2 base endpoints should be hit. Other
        # endpoints return a clean 4001 so dev knows to fall back.
        raise BizException(ErrorCode.NOT_FOUND, message="endpoint mock-only in V2")
    return p


# --------------------------------------------------------------------------- #
# 1. POST /api/v2/sms/send                                                    #
# --------------------------------------------------------------------------- #
@router.post(
    "/send",
    response_model=ApiResponse[SendCodeData],
    summary="Send a 6-digit SMS code (mock mode: returns raw code in response)",
)
async def send_sms(body: SendCodeRequest) -> ApiResponse[SendCodeData]:
    """Mock-mode: prints `code` to stdout and echoes it in the response.

    Production swap (V2.1, Tencent Cloud): `code` will be null and the
    console.log will be replaced by an HTTP call to tencentcloud-sdk.
    """
    provider = _provider()
    settings = get_settings()
    result = await provider.send_sms(
        phone=body.phone, phone_country=body.phone_country, purpose=body.purpose
    )
    if not result.get("ok"):
        raise BizException(
            ErrorCode.SMS_GATEWAY_DOWN, message=result.get("error") or "SMS gateway down"
        )
    return ApiResponse[SendCodeData](
        code="1000",
        message="OK",
        data=SendCodeData(
            phone=body.phone,
            phone_country=body.phone_country,
            purpose=body.purpose,
            message_id=result["message_id"],
            expires_in=result["expires_in"],
            template_id="mock_default",
            code=result["code"] if settings.sms_channel == "mock" else None,
        ),
    )


# --------------------------------------------------------------------------- #
# 2. POST /api/v2/sms/verify                                                  #
# --------------------------------------------------------------------------- #
@router.post(
    "/verify",
    response_model=ApiResponse[VerifyCodeData],
    summary="Verify a 6-digit SMS code, mint a JWT on success",
)
async def verify_sms(body: VerifyCodeRequest) -> ApiResponse[VerifyCodeData]:
    """Verify against the in-memory store; on success mint an access token
    using a synthetic user_id=0 (mock-mode dev convenience).

    Production swap: user_id should come from the User table lookup
    keyed by (phone, phone_country).
    """
    provider = _provider()
    try:
        ok = await provider.verify_code(
            phone=body.phone,
            phone_country=body.phone_country,
            code=body.code,
            purpose=body.purpose,
        )
    except NoCodeOnFile as exc:
        raise BizException(ErrorCode.SMS_CODE_INVALID, message=str(exc)) from exc
    except CodeExpired as exc:
        raise BizException(ErrorCode.SMS_CODE_EXPIRED, message=str(exc)) from exc
    except CodeMismatch as exc:
        raise BizException(ErrorCode.SMS_CODE_INVALID, message=str(exc)) from exc

    if not ok:
        raise BizException(ErrorCode.SMS_CODE_INVALID, message="verification failed")

    # Mock convenience — mint a JWT so dev console can hit /me directly.
    # user_id=0 is the "anonymous / sms-mock" sentinel; production
    # resolve() looks the user up by phone.
    settings = get_settings()
    token, exp = create_access_token(user_id=0, settings=settings)
    expires_in = max(0, int((exp - datetime.now(timezone.utc)).total_seconds()))
    _log.info(
        "sms verify OK phone={}{} purpose={} expires_in={}",
        body.phone_country, body.phone, body.purpose, expires_in,
    )
    return ApiResponse[VerifyCodeData](
        code="1000",
        message="OK",
        data=VerifyCodeData(
            verified=True,
            phone=body.phone,
            phone_country=body.phone_country,
            purpose=body.purpose,
            access_token=token,
            token_type="Bearer",
            expires_in=expires_in,
        ),
    )


# --------------------------------------------------------------------------- #
# 3. GET /api/v2/sms/{message_id}                                             #
# --------------------------------------------------------------------------- #
@router.get(
    "/{message_id}",
    response_model=ApiResponse[MessageStatusData],
    summary="Query SMS send status by message_id (mock: sent / unknown)",
)
async def get_sms_status(
    message_id: str = Path(..., min_length=4, max_length=64),
) -> ApiResponse[MessageStatusData]:
    """Mock returns one of two statuses:

      - `sent`    — message_id matches an active (non-expired) entry
      - `unknown` — never issued, already verified, or already expired

    Production swap (V2.1): hit Tencent's `SendStatus` API.
    """
    provider = _provider()
    info = provider.get_message_status(message_id) or {"message_id": message_id, "status": "unknown"}
    return ApiResponse[MessageStatusData](code="1000", message="OK", data=MessageStatusData(**info))


# --------------------------------------------------------------------------- #
# 4. POST /api/v2/sms/template                                                #
# --------------------------------------------------------------------------- #
@router.post(
    "/template",
    response_model=ApiResponse[TemplateData],
    summary="Register a template (mock-only, in-memory; V2.1 wires Tencent)",
)
async def register_template(body: RegisterTemplateRequest) -> ApiResponse[TemplateData]:
    """Mock-only — keeps the in-memory template registry up to date.

    V2.1 swap: POST to Tencent Cloud console template API + persist a
    mirror row in `sms_templates` table.
    """
    provider = _provider()
    provider.register_template(
        template_id=body.template_id,
        purpose=body.purpose,
        locale=body.locale,
        body=body.body,
    )
    return ApiResponse[TemplateData](
        code="1000",
        message="OK",
        data=TemplateData(
            template_id=body.template_id,
            purpose=body.purpose,
            locale=body.locale,
            body=body.body,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )