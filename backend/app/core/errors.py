"""
Centralized error-code registry + custom exception hierarchy.

Error codes follow V2 §9.3 (1xxx-7xxx). Each domain gets a base code
and derived codes are sequential.

Usage:
    raise BizException(ErrorCode.AUTH_INVALID_CREDENTIALS)

    @app.exception_handler(BizException)
    async def handle_biz(request, exc): ...
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException, status


# ------------------------------------------------------------------ #
# Error code registry                                                #
# ------------------------------------------------------------------ #
class ErrorCode(str, Enum):
    # 1xxx — 通用
    OK = "1000"
    INVALID_PARAMS = "1001"
    MISSING_FIELD = "1002"
    INVALID_FORMAT = "1003"
    NOT_FOUND = "1004"
    UNAUTHORIZED = "1005"
    FORBIDDEN = "1006"
    CONFLICT = "1007"
    RATE_LIMIT = "1009"
    SERVER_ERROR = "1010"

    # 2xxx — Auth
    AUTH_INVALID_CREDENTIALS = "2001"
    SMS_CODE_INVALID = "2002"
    USER_ALREADY_EXISTS = "2003"
    PASSWORD_TOO_WEAK = "2004"
    ACCOUNT_DISABLED = "2005"
    REFRESH_TOKEN_INVALID = "2006"
    REFRESH_TOKEN_EXPIRED = "2007"
    SMS_CODE_EXPIRED = "2008"
    SMS_CODE_USED = "2009"
    SMS_RATE_LIMIT = "2010"

    # 3xxx — User
    USER_NOT_FOUND = "3001"
    NICKNAME_TAKEN = "3002"

    # 4xxx — Order (V2 §4.2)
    ORDER_NOT_FOUND = "4001"
    ORDER_NOT_CANCELLABLE = "4002"
    ORDER_INVALID_VISA_TYPE = "4003"
    ORDER_DESTINATION_DISABLED = "4004"
    ORDER_MATERIALS_NOT_FOUND = "4005"
    ORDER_MATERIAL_NOT_OWNED = "4006"
    ORDER_ALREADY_EXISTS = "4007"
    ORDER_INVALID_STATE = "4008"
    ORDER_CREATE_FAILED = "4009"
    ORDER_NOT_EDITABLE = "4010"  # checklist/edit forbidden (status != created)
    ORDER_SIGNATURE_MISMATCH = "4011"  # submit signature does not match server-side (4011 chosen: 4003 already taken by ORDER_INVALID_VISA_TYPE)
    PAYMENT_NOT_FOUND = "4012"  # GET /api/v2/payment/{order_no} but order has no payment record yet (or order_no unknown)
    PAYMENT_ALREADY_PAID = "4013"  # POST /api/v2/payment/{order_no}/close but order is already paid (refund needed)
    PAYMENT_AMOUNT_INVALID = "4014"  # POST /api/v2/payment/create amount_cents <= 0

    # 7xxx — 第三方
    SMS_GATEWAY_DOWN = "7001"


# HTTP status mapping (defaults; can be overridden when raising)
_ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.OK: status.HTTP_200_OK,
    ErrorCode.INVALID_PARAMS: status.HTTP_400_BAD_REQUEST,
    ErrorCode.MISSING_FIELD: status.HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_FORMAT: status.HTTP_400_BAD_REQUEST,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.RATE_LIMIT: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.SERVER_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.AUTH_INVALID_CREDENTIALS: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.SMS_CODE_INVALID: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.USER_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    ErrorCode.PASSWORD_TOO_WEAK: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.ACCOUNT_DISABLED: status.HTTP_403_FORBIDDEN,
    ErrorCode.REFRESH_TOKEN_INVALID: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.REFRESH_TOKEN_EXPIRED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.SMS_CODE_EXPIRED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.SMS_CODE_USED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.SMS_RATE_LIMIT: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.USER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.NICKNAME_TAKEN: status.HTTP_409_CONFLICT,
    # Order domain mappings
    ErrorCode.ORDER_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.ORDER_NOT_CANCELLABLE: status.HTTP_409_CONFLICT,
    ErrorCode.ORDER_INVALID_VISA_TYPE: status.HTTP_400_BAD_REQUEST,
    ErrorCode.ORDER_DESTINATION_DISABLED: status.HTTP_400_BAD_REQUEST,
    ErrorCode.ORDER_MATERIALS_NOT_FOUND: status.HTTP_400_BAD_REQUEST,
    ErrorCode.ORDER_MATERIAL_NOT_OWNED: status.HTTP_403_FORBIDDEN,
    ErrorCode.ORDER_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    ErrorCode.ORDER_INVALID_STATE: status.HTTP_409_CONFLICT,
    ErrorCode.ORDER_CREATE_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.ORDER_NOT_EDITABLE: status.HTTP_409_CONFLICT,
    ErrorCode.ORDER_SIGNATURE_MISMATCH: status.HTTP_400_BAD_REQUEST,
    ErrorCode.PAYMENT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.PAYMENT_ALREADY_PAID: status.HTTP_409_CONFLICT,
    ErrorCode.PAYMENT_AMOUNT_INVALID: status.HTTP_400_BAD_REQUEST,
    ErrorCode.SMS_GATEWAY_DOWN: status.HTTP_502_BAD_GATEWAY,
}


# ------------------------------------------------------------------ #
# Exception hierarchy                                                #
# ------------------------------------------------------------------ #
class BizException(HTTPException):
    """Business-domain exception mapped to an HTTP response.

    Example:
        raise BizException(ErrorCode.USER_ALREADY_EXISTS,
                          message="Phone already registered",
                          data={"phone": "13800000000"})
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        status_code: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or code.name.replace("_", " ").title()
        self.data = data or {}
        super().__init__(
            status_code=status_code or _ERROR_HTTP_STATUS[code],
            detail=self._build_detail(),
        )

    def _build_detail(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "data": self.data,
        }


def build_error_payload(
    code: ErrorCode,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the standard error payload (used by handlers & tests)."""
    return {
        "code": code.value,
        "message": message or code.name.replace("_", " ").title(),
        "data": data or {},
    }
