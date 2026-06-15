"""Admin API schemas — login, user/order management, config, logs."""
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Auth                                                                       #
# --------------------------------------------------------------------------- #
class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AdminTokenData(BaseModel):
    admin_id: int
    username: str
    role: str = "admin"


class AdminTokenOut(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds


# --------------------------------------------------------------------------- #
# User management                                                            #
# --------------------------------------------------------------------------- #
class UserOut(BaseModel):
    id: int
    uuid: str
    phone: str
    phone_country: str
    nickname: Optional[str]
    language_pref: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


def _mask_phone(phone: str) -> str:
    """Mask phone number: show only last 4 digits (e.g. ****5678)."""
    if not phone or len(phone) <= 4:
        return "****"
    return "*" * (len(phone) - 4) + phone[-4:]


class UserOutSafe(BaseModel):
    """Admin-safe user view: phone masked to last 4 digits (OWASP A1 privacy)."""
    id: int
    uuid: str
    phone: str = Field(..., description="Masked: last 4 digits only")
    phone_country: str
    nickname: Optional[str]
    language_pref: str
    status: str
    created_at: datetime

    @classmethod
    def from_user_out(cls, user: UserOut) -> "UserOutSafe":
        return cls(
            id=user.id,
            uuid=user.uuid,
            phone=_mask_phone(user.phone),
            phone_country=user.phone_country,
            nickname=user.nickname,
            language_pref=user.language_pref,
            status=user.status,
            created_at=user.created_at,
        )

    class Config:
        from_attributes = True


class PaginatedUserList(BaseModel):
    items: list[UserOut]
    page: int
    page_size: int
    total: int
    total_pages: int


# --------------------------------------------------------------------------- #
# Order management                                                           #
# --------------------------------------------------------------------------- #
class OrderOut(BaseModel):
    id: int
    uuid: str
    order_no: str
    user_id: int
    destination_id: int
    visa_type: str
    status: str
    total_amount: float
    currency: str
    rpa_task_id: Optional[str]
    aff_code: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderDetailOut(OrderOut):
    submitted_at: Optional[datetime]
    reviewed_at: Optional[datetime]
    closed_at: Optional[datetime]
    applicant_data: Optional[str]
    material_ids: Optional[str]


class PaginatedOrderList(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class UpdateOrderStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=24)
    note: Optional[str] = Field(None, max_length=256)


# --------------------------------------------------------------------------- #
# Country config                                                             #
# --------------------------------------------------------------------------- #
class CountryOut(BaseModel):
    id: int
    country_code: str
    country_name_zh: str
    country_name_en: str
    enabled: bool
    base_url: Optional[str]
    form_path: Optional[str]
    rpa_config: Optional[str]
    visa_types: Optional[str]
    fee_usd: Optional[float]
    processing_days: Optional[int]
    extra: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateCountryRequest(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=8)
    country_name_zh: str = Field(..., min_length=1, max_length=128)
    country_name_en: str = Field(..., min_length=1, max_length=128)
    enabled: bool = True
    base_url: Optional[str] = None
    form_path: Optional[str] = None
    rpa_config: Optional[str] = None
    visa_types: Optional[list[str]] = None
    fee_usd: Optional[float] = None
    processing_days: Optional[int] = None
    extra: Optional[str] = None


class UpdateCountryRequest(BaseModel):
    country_name_zh: Optional[str] = Field(None, max_length=128)
    country_name_en: Optional[str] = Field(None, max_length=128)
    enabled: Optional[bool] = None
    base_url: Optional[str] = None
    form_path: Optional[str] = None
    rpa_config: Optional[str] = None
    visa_types: Optional[list[str]] = None
    fee_usd: Optional[float] = None
    processing_days: Optional[int] = None
    extra: Optional[str] = None


# --------------------------------------------------------------------------- #
# Validation rules                                                           #
# --------------------------------------------------------------------------- #
class ValidationRuleOut(BaseModel):
    id: int
    code: str
    rule_type: str
    severity: str
    message_key: str
    params: Optional[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdateValidationRulesRequest(BaseModel):
    rules: list[dict[str, Any]] = Field(..., min_length=1)


# --------------------------------------------------------------------------- #
# RPA config                                                                 #
# --------------------------------------------------------------------------- #
class RpaConfigOut(BaseModel):
    rate_limits: dict[str, Any]
    timeouts: dict[str, Any]
    retry: dict[str, Any]
    captcha: dict[str, Any]
    session: dict[str, Any]
    countries: dict[str, Any]
    mock_mode: bool


class UpdateRpaConfigRequest(BaseModel):
    rate_limits: Optional[dict[str, Any]] = None
    timeouts: Optional[dict[str, Any]] = None
    retry: Optional[dict[str, Any]] = None
    captcha: Optional[dict[str, Any]] = None
    session: Optional[dict[str, Any]] = None
    countries: Optional[dict[str, Any]] = None
    mock_mode: Optional[bool] = None


# --------------------------------------------------------------------------- #
# Audit logs                                                                 #
# --------------------------------------------------------------------------- #
class AuditLogOut(BaseModel):
    id: int
    uuid: str
    actor_type: str
    actor_id: Optional[int]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    payload: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedAuditLogList(BaseModel):
    items: list[AuditLogOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedCountryList(BaseModel):
    items: list[dict]
    page: int
    page_size: int
    total: int
    total_pages: int


# --------------------------------------------------------------------------- #
# RPA stats                                                                  #
# --------------------------------------------------------------------------- #
class RpaStatsOut(BaseModel):
    """Realtime RPA pipeline stats — derived from the in-memory scheduler.

    Stats cover the running process only (no historical persistence). This
    is acceptable for an operations dashboard fed by the live scheduler.
    """
    today_visits: int = Field(..., ge=0, description="IP visits today (since 00:00 UTC)")
    queued_tasks: int = Field(..., ge=0, description="Tasks currently in IDLE / SUBMITTING / WAITING")
    failure_rate_24h: float = Field(
        ..., ge=0.0, le=1.0,
        description="Failed / total task ratio over the last 24 hours"
    )
    success_count_24h: int = Field(..., ge=0, description="Tasks completed DONE in the last 24h")
    failed_count_24h: int = Field(..., ge=0, description="Tasks ended FAILED in the last 24h")
    total_count_24h: int = Field(..., ge=0, description="Total terminal tasks in the last 24h")
    active_accounts: int = Field(..., ge=0, description="Accounts with at least one running task")
    sample_window_seconds: int = Field(
        86400, ge=1,
        description="Window size used for the 24h failure rate (seconds)"
    )
    generated_at: datetime = Field(..., description="Server-side generation timestamp (UTC)")


# --------------------------------------------------------------------------- #
# Dashboard stats                                                              #
# --------------------------------------------------------------------------- #
class DashboardStatsOut(BaseModel):
    """Aggregated stats for the admin dashboard summary panel."""
    today_new_orders: int = Field(..., ge=0, description="Orders created today (UTC)")
    week_new_orders: int = Field(..., ge=0, description="Orders created this week (Mon 00:00 UTC)")
    pending_orders: int = Field(..., ge=0, description="Orders in 'created' or 'submitted' status")
    completed_orders: int = Field(..., ge=0, description="Orders in 'approved' or 'closed' status")
    payment_success_rate: float = Field(
        ..., ge=0.0, le=1.0,
        description="orders with submitted_at not null / total orders (0.0 if no orders)"
    )
    generated_at: datetime = Field(..., description="Server-side generation timestamp (UTC)")
    cached: bool = Field(False, description="Whether this response was served from cache")
