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
    """登录返回（W34：含权限信息）"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    username: str = ""
    role_name: str = ""
    permissions: list[str] = Field(default_factory=list)  # seconds


# --------------------------------------------------------------------------- #
# User management                                                            #
# --------------------------------------------------------------------------- #
class UserOut(BaseModel):
    id: int
    uuid: str
    email: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    phone_country: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    language_pref: str = "zh-CN"
    status: str
    mfa_enabled: bool = False
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _mask_phone(phone: Optional[str]) -> str:
    """Mask phone number: show only last 4 digits (e.g. ****5678)."""
    if not phone or len(phone) <= 4:
        return "****"
    return "*" * (len(phone) - 4) + phone[-4:]


def _mask_email(email: Optional[str]) -> Optional[str]:
    """Mask email: keep first 2 chars + ***@domain (e.g. ab***@gmail.com)."""
    if not email or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if not local:
        return email
    if len(local) <= 2:
        head = local
    else:
        head = local[:2]
    return f"{head}***@{domain}"


class UserOutSafe(UserOut):
    """Admin-safe user view: phone/email masked to last 4 / first 2 chars
    (OWASP A1 privacy). All other fields pass through unchanged.
    """
    # Overrides the parent fields with masked values
    phone: str = Field(..., description="Masked: last 4 digits only")
    email: Optional[str] = Field(None, description="Masked: first 2 chars + ***@domain")

    @classmethod
    def from_raw(cls, raw: dict) -> "UserOutSafe":
        """Build a safe view directly from a raw user dict (service output).

        We don't reuse `UserOut` here because the masked fields diverge.
        """
        return cls(
            id=raw["id"],
            uuid=raw["uuid"],
            email=_mask_email(raw.get("email")),
            username=raw.get("username"),
            phone=_mask_phone(raw.get("phone")),
            phone_country=raw.get("phone_country"),
            nickname=raw.get("nickname"),
            avatar_url=raw.get("avatar_url"),
            language_pref=raw.get("language_pref") or "zh-CN",
            status=raw.get("status") or "active",
            mfa_enabled=bool(raw.get("mfa_enabled", False)),
            last_login_at=raw.get("last_login_at"),
            last_login_ip=raw.get("last_login_ip"),
            created_at=raw.get("created_at"),
            updated_at=raw.get("updated_at"),
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
# C-端用户管理 (W36: 详情页 + 操作能力)                                          #
# --------------------------------------------------------------------------- #
class UserDetailOut(UserOutSafe):
    """C-端用户详情（含统计字段）。继承自 UserOutSafe 自动脱敏。"""
    order_count: int = Field(0, ge=0, description="该用户的订单总数")
    material_count: int = Field(0, ge=0, description="该用户的材料总数")


class UpdateUserRequest(BaseModel):
    """修改 C-端用户基本信息（仅 nickname / language_pref / avatar_url）。
    email / username / password 不允许在此接口修改（走专门接口）。"""
    nickname: Optional[str] = Field(None, max_length=64)
    language_pref: Optional[str] = Field(None, max_length=8)
    avatar_url: Optional[str] = Field(None, max_length=512)


class ResetPasswordResponse(BaseModel):
    """重置密码后返回一次性的明文密码（不再返回）。"""
    user_id: int
    username: Optional[str]
    new_password: str = Field(..., description="一次性明文，UI 弹窗提示用户复制保存")
    reset_at: datetime


class UserOrderItem(BaseModel):
    """用户关联订单中的一条（精简字段）"""
    id: int
    order_no: str
    visa_type: str
    status: str
    total_amount: float
    currency: str
    destination_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedUserOrderList(BaseModel):
    items: list[UserOrderItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class UserActionResponse(BaseModel):
    """disable / restore / update_user 的统一响应。"""
    user_id: int
    status: str
    message: str = "OK"
    updated_at: Optional[datetime] = None


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


class OrderPaymentInfo(BaseModel):
    """支付流水信息 — 从 order.extra JSON 中解析，订单与资金流分开展示"""
    trade_no: Optional[str] = Field(None, description="支付流水号")
    status: str = Field("none", description="none | pending | paid | closed | failed")
    paid_at: Optional[datetime] = Field(None, description="支付成功时间")
    amount_cents: int = Field(0, description="支付金额（分）")
    currency: str = Field("USD", description="币种")
    code_url: Optional[str] = Field(None, description="支付链接（待支付时展示）")
    expired_at: Optional[datetime] = Field(None, description="支付链接过期时间")

    class Config:
        from_attributes = True


class AuditLogItem(BaseModel):
    """订单详情中的审计日志条目"""
    id: int
    actor_type: str
    actor_id: Optional[int]
    action: str
    payload: Optional[str]
    created_at: datetime


class OrderDetailOut(OrderOut):
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    applicant_data: Optional[str] = None
    material_ids: Optional[str] = None
    destination_url: Optional[str] = None
    status_history: list[dict] = Field(default_factory=list)
    allowed_next_statuses: list[str] = Field(default_factory=list)
    payment: Optional[OrderPaymentInfo] = Field(None, description="支付流水（独立展示）")
    audit_logs: list[AuditLogItem] = Field(default_factory=list, description="完整审计日志")


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
    display_order: int = 0
    base_url: Optional[str]
    form_path: Optional[str]
    form_template_url: Optional[str] = None
    rpa_config: Optional[str]
    visa_types: Optional[list[str]] = None
    fee_usd: Optional[float]
    processing_days: Optional[int]
    description: Optional[str] = None
    flag_emoji: Optional[str] = None
    capital_city: Optional[str] = None
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
    display_order: int = Field(0, ge=0)
    base_url: Optional[str] = None
    form_path: Optional[str] = None
    form_template_url: Optional[str] = None
    rpa_config: Optional[str] = None
    visa_types: Optional[list[str]] = None
    fee_usd: Optional[float] = None
    processing_days: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    flag_emoji: Optional[str] = Field(None, max_length=16)
    capital_city: Optional[str] = Field(None, max_length=128)
    extra: Optional[str] = None


class UpdateCountryRequest(BaseModel):
    country_name_zh: Optional[str] = Field(None, max_length=128)
    country_name_en: Optional[str] = Field(None, max_length=128)
    enabled: Optional[bool] = None
    display_order: Optional[int] = Field(None, ge=0)
    base_url: Optional[str] = None
    form_path: Optional[str] = None
    form_template_url: Optional[str] = None
    rpa_config: Optional[str] = None
    visa_types: Optional[list[str]] = None
    fee_usd: Optional[float] = None
    processing_days: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    flag_emoji: Optional[str] = Field(None, max_length=16)
    capital_city: Optional[str] = Field(None, max_length=128)
    extra: Optional[str] = None


class ReorderCountryItem(BaseModel):
    id: int = Field(..., ge=1)
    display_order: int = Field(..., ge=0)


class ReorderCountriesRequest(BaseModel):
    """Body for POST /config/countries/reorder.

    Items are the new ordering — server writes each (id → display_order)
    mapping in a single transaction.
    """
    orders: list[ReorderCountryItem] = Field(..., min_length=1)


class ToggleCountryRequest(BaseModel):
    enabled: bool


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
    # W35: join users/admin_users 后填入, 列表/详情页展示
    actor_name: Optional[str] = Field(None, description="操作者姓名/账号")
    target_name: Optional[str] = Field(None, description="目标对象名称")

    class Config:
        from_attributes = True


class PaginatedAuditLogList(BaseModel):
    items: list[AuditLogOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class LogDetailOut(BaseModel):
    """日志详情 — payload 解析为 dict 后返回"""
    id: int
    uuid: str
    actor_type: str
    actor_id: Optional[int]
    actor_name: Optional[str] = None
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    target_name: Optional[str] = None
    payload: Optional[str] = None
    payload_json: Optional[Any] = Field(None, description="payload 字段解析后的 dict/list")
    created_at: datetime


class LogActionListOut(BaseModel):
    """返回所有出现过的 action 列表(用于筛选下拉)"""
    actions: list[str]
    actor_types: list[str]
    target_types: list[str]


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
    # ---- V2 §4.1.4 / §4.3.5 / §4.7 additions ---- #
    cleanup_stats: "CleanupStatsOut" = Field(
        default_factory=lambda: CleanupStatsOut(
            temp_candidates=0, archive_candidates=0,
            pending_destroy_users=0, storage_bytes=0,
            generated_at=datetime.utcnow(),
        ),
        description="可清理量统计 (临时文件 / 归档文件 / 待注销用户)",
    )
    rpa_health: str = Field(
        "healthy", description="RPA 调度器健康度: healthy | degraded | down"
    )
    disk_usage_percent: float = Field(
        0.0, ge=0.0, le=100.0,
        description="磁盘使用率 (0-100), material_storage_root",
    )
    db_size_bytes: int = Field(
        0, ge=0, description="SQLite DB 文件大小 (字节); Postgres 下取表大小估算"
    )


# --------------------------------------------------------------------------- #
# Role & Admin User management (W34)                                          #
# --------------------------------------------------------------------------- #
class AdminRoleOut(BaseModel):
    id: int
    name: str
    code: str
    permissions: list[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminUserOut(BaseModel):
    """管理员用户（密码不返回）"""
    id: int
    username: str
    role_id: int
    role_name: Optional[str] = None
    role_code: Optional[str] = None
    permissions: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedAdminUserList(BaseModel):
    items: list[AdminUserOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=32)
    permissions: list[str] = Field(default_factory=list)
    description: Optional[str] = Field(None, max_length=256)


class UpdateRoleRequest(BaseModel):
    description: Optional[str] = Field(None, max_length=256)
    permissions: Optional[list[str]] = None
    is_active: Optional[bool] = None


class CreateAdminUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    role_id: int = Field(..., ge=1)


class UpdateAdminUserRequest(BaseModel):
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    role_id: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class AdminTokenWithPermissions(BaseModel):
    """登录成功后返回的 token 信息（含权限）"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    username: str
    role_name: str
    permissions: list[str]
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


# --------------------------------------------------------------------------- #
# Payment flow (资金流)                                                        #
# --------------------------------------------------------------------------- #
class PaymentFlowOut(BaseModel):
    """资金流列表中的一条记录"""
    order_id: int
    order_no: str
    user_id: int
    trade_no: Optional[str] = Field(None, description="支付流水号")
    status: str = Field("none", description="none | pending | paid | closed | failed")
    amount_cents: int = Field(0, description="支付金额（分）")
    currency: str = Field("USD", description="币种")
    paid_at: Optional[datetime] = Field(None, description="支付成功时间")
    created_at: datetime = Field(..., description="订单创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")


class PaginatedPaymentList(BaseModel):
    items: list[PaymentFlowOut]
    page: int
    page_size: int
    total: int
    total_pages: int


# --------------------------------------------------------------------------- #
# Cleanup & dashboard actions (V2 §4.1.4 + §4.3.5)                              #
# --------------------------------------------------------------------------- #
class CleanupStatsOut(BaseModel):
    """当前可清理量 — 前端 dashboard / cleanup 页面用."""
    temp_candidates: int = Field(..., ge=0, description="可清理的临时文件数 (>24h, storage_key 含 tmp)")
    archive_candidates: int = Field(..., ge=0, description="可清理的归档文件数 (>180h, archived=true 或 storage_key 含 archive)")
    pending_destroy_users: int = Field(..., ge=0, description="待注销用户数 (status=pending_destroy 且 updated_at > 72h)")
    storage_bytes: int = Field(..., ge=0, description="当前数据库活跃文件总字节数")
    last_run_at: Optional[datetime] = Field(None, description="上次清理任务执行时间 (UTC)")
    generated_at: datetime = Field(..., description="服务端生成时间 (UTC)")


class CleanupResultOut(BaseModel):
    """单次清理操作的执行结果."""
    action: str = Field(..., description="temp_files | archived_files | pending_destroys")
    deleted_count: int = Field(..., ge=0)
    freed_bytes: int = Field(..., ge=0, description="释放的磁盘字节数")
    duration_ms: int = Field(..., ge=0, description="执行耗时 (ms)")
    affected_users: list[int] = Field(default_factory=list, description="pending_destroy 时涉及的 user_id 列表")
    finished_at: datetime = Field(..., description="完成时间 (UTC)")
    errors: list[str] = Field(default_factory=list, description="逐项错误信息 (非致命)")


class DashboardActionResultOut(BaseModel):
    """Dashboard 一键操作的返回 (清缓存 / 暂停 RPA / 恢复 RPA)."""
    action: str = Field(..., description="cache_clear | rpa_pause | rpa_resume")
    success: bool
    message: str
    affected_items: int = Field(0, ge=0, description="受影响条目数 (清缓存的 key 数等)")
    finished_at: datetime = Field(..., description="完成时间 (UTC)")


# --------------------------------------------------------------------------- #
# i18n overrides (V0 §4.4.4 多语种文案统一管理)                                #
# --------------------------------------------------------------------------- #
class I18nOverrideOut(BaseModel):
    id: int
    locale: str
    key: str
    value: str
    original_value: Optional[str] = None
    updated_by_admin_id: Optional[int] = None
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class CreateI18nOverrideRequest(BaseModel):
    locale: str = Field(..., min_length=2, max_length=16, description="zh-CN / en / vi / id")
    key: str = Field(..., min_length=1, max_length=256)
    value: str = Field(..., min_length=1)
    original_value: Optional[str] = None


class UpdateI18nOverrideRequest(BaseModel):
    value: Optional[str] = Field(None, min_length=1)
    original_value: Optional[str] = None


class PaginatedI18nOverrideList(BaseModel):
    items: list[I18nOverrideOut]
    page: int
    page_size: int
    total: int
    total_pages: int


class ImportI18nOverridesRequest(BaseModel):
    """批量导入覆盖 — body: {"locale": "en", "entries": {"key1": "value1", ...}}"""
    locale: str = Field(..., min_length=2, max_length=16)
    entries: dict[str, str] = Field(..., min_length=1, description="key → value 字典")
