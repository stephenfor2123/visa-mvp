"""
/api/v2/admin/* — Admin panel backend (W14-3).

Endpoints (all admin-only, protected by verify_admin_token):
  - POST   /api/v2/admin/login                           — admin login
  - GET    /api/v2/admin/users                          — paginated user list
  - GET    /api/v2/admin/users/{id}                    — user detail
  - DELETE /api/v2/admin/users/{id}                    — soft-delete user
  - GET    /api/v2/admin/orders                         — paginated order list
  - GET    /api/v2/admin/orders/{id}                    — order detail
  - PUT    /api/v2/admin/orders/{id}/status             — update order status
  - GET    /api/v2/admin/config/countries               — list country config
  - POST   /api/v2/admin/config/countries               — create country
  - PUT    /api/v2/admin/config/countries/{id}          — update country
  - DELETE /api/v2/admin/config/countries/{id}          — offline country
  - GET    /api/v2/admin/config/validation-rules         — list AI rules
  - PUT    /api/v2/admin/config/validation-rules         — update rules
  - GET    /api/v2/admin/config/rpa                     — read RPA config
  - PUT    /api/v2/admin/config/rpa                     — update RPA config
  - GET    /api/v2/admin/stats/rpa                      — realtime RPA stats (W14-6)
  - GET    /api/v2/admin/stats/dashboard                — dashboard summary stats (W16)
  - GET    /api/v2/admin/logs                           — paginated audit logs
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.middleware.admin_auth import verify_admin_token, verify_admin_token_with_db
from app.core.permissions import PERMISSIONS, PERM_GROUPS
from app.middleware.admin_auth import require_perm
from app.schemas.admin import (
    AdminLoginRequest,
    AdminTokenData,
    AdminTokenOut,
    AdminRoleOut,
    AdminUserOut,
    CreateRoleRequest,
    UpdateRoleRequest,
    CountryOut,
    CreateCountryRequest,
    CreateAdminUserRequest,
    UpdateAdminUserRequest,
    PaginatedAuditLogList,
    PaginatedCountryList,
    PaginatedOrderList,
    PaginatedPaymentList,
    PaginatedAdminUserList,
    PaginatedUserList,
    RpaConfigOut,
    RpaStatsOut,
    ReorderCountriesRequest,
    ToggleCountryRequest,
    UpdateCountryRequest,
    UpdateOrderStatusRequest,
    UpdateRpaConfigRequest,
    UpdateValidationRulesRequest,
    ValidationRuleOut,
    AuditLogOut,
    DashboardStatsOut,
    OrderDetailOut,
    OrderOut,
    PaymentFlowOut,
    PaymentFlowStats,
    UserOut,
    UserOutSafe,
    I18nOverrideOut,
    CreateI18nOverrideRequest,
    UpdateI18nOverrideRequest,
    PaginatedI18nOverrideList,
    ImportI18nOverridesRequest,
    UserDetailOut,
    UpdateUserRequest,
    ResetPasswordResponse,
    UserActionResponse,
    PaginatedUserOrderList,
    DashboardSummaryOut,
    DashboardTrendOut,
    DashboardFunnelOut,
    DashboardTopCountriesOut,
    DashboardAlertsOut,
)
from app.schemas.common import ApiResponse
from app.services.admin_service import AdminService
from app.services.admin_dashboard_service import AdminDashboardService


# Module-level router (W14-3 left this declaration missing, breaking import).
router = APIRouter(prefix="/admin", tags=["admin"])


# --------------------------------------------------------------------------- #
# Auth                                                                       #
# --------------------------------------------------------------------------- #
@router.post(
    "/login",
    # 注意: login 不需要 perm (任何人可登录尝试, 失败返 401)
    # W34: DB-first, fallback to env password
    response_model=ApiResponse[AdminTokenOut],
    summary="Admin login (W34: DB-first, fallback to env password)",
)
async def admin_login(
    body: AdminLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[AdminTokenOut]:
    svc = AdminService(db)
    result = await svc.login(username=body.username, password=body.password)
    return ApiResponse[AdminTokenOut](
        code="1000", message="OK", data=AdminTokenOut(**result)
    )


# --------------------------------------------------------------------------- #
# Permission registry (单一权威源,前端 perm grid 用)                          #
# --------------------------------------------------------------------------- #
@router.get(
    "/permissions",
    # 任何登录的 admin 都能查 perm 注册表 (前端 perm grid 渲染用)
    # 不强制 perm, 否则 role.manage 之外的 staff 看不到自己被分配了哪些 perm
    response_model=ApiResponse[dict],
    summary="List all permission codes (grouped) — 前端 perm grid 渲染用",
)
async def list_permissions(
    _admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[dict]:
    grouped: dict[str, list[dict]] = {g: [] for g in set(PERM_GROUPS.values())}
    for p in PERMISSIONS:
        grouped[p["group"]].append({
            "code": p["code"],
            "label_key": p["label_key"],
            "description": p["description"],
        })
    return ApiResponse[dict](
        code="1000", message="OK",
        data={"groups": grouped, "groups_order": list(PERM_GROUPS.keys())},
    )


# --------------------------------------------------------------------------- #
# Role & admin-user management (W34)                                         #
# --------------------------------------------------------------------------- #
@router.get(
    "/roles",
    dependencies=[Depends(require_perm("role.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[list[AdminRoleOut]],
    summary="List all roles",
)
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[list[AdminRoleOut]]:
    svc = AdminService(db)
    out = await svc.list_roles()
    return ApiResponse[list[AdminRoleOut]](
        code="1000", message="OK", data=[AdminRoleOut(**r) for r in out]
    )


@router.post(
    "/roles",
    dependencies=[Depends(require_perm("role.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[AdminRoleOut],
    status_code=201,
    summary="Create a new role",
)
async def create_role(
    body: CreateRoleRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[AdminRoleOut]:
    svc = AdminService(db)
    out = await svc.create_role(data=body.model_dump())
    return ApiResponse[AdminRoleOut](code="1000", message="OK", data=AdminRoleOut(**out))


@router.put(
    "/roles/{role_id}",
    dependencies=[Depends(require_perm("role.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[AdminRoleOut],
    summary="Update a role (description / permissions / is_active)",
)
async def update_role(
    role_id: int = Path(..., ge=1),
    body: UpdateRoleRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[AdminRoleOut]:
    svc = AdminService(db)
    out = await svc.update_role(role_id=role_id, data=body.model_dump(exclude_none=True))
    return ApiResponse[AdminRoleOut](code="1000", message="OK", data=AdminRoleOut(**out))


@router.delete(
    "/roles/{role_id}",
    dependencies=[Depends(require_perm("role.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Soft-delete (deactivate) a role",
)
async def delete_role(
    role_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    await svc.delete_role(role_id=role_id)
    return ApiResponse[dict](code="1000", message="OK", data={"message": "角色已停用"})


@router.get(
    "/admin-users",
    dependencies=[Depends(require_perm("role.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedAdminUserList],
    summary="Paginated admin user list",
)
async def list_admin_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PaginatedAdminUserList]:
    svc = AdminService(db)
    out = await svc.list_admin_users(page=page, page_size=page_size)
    return ApiResponse[PaginatedAdminUserList](
        code="1000", message="OK",
        data=PaginatedAdminUserList(
            items=[AdminUserOut(**u) for u in out["items"]],
            page=out["page"], page_size=out["page_size"],
            total=out["total"], total_pages=out["total_pages"],
        ),
    )


@router.post(
    "/admin-users",
    dependencies=[Depends(require_perm("role.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[AdminUserOut],
    status_code=201,
    summary="Create admin user",
)
async def create_admin_user(
    body: CreateAdminUserRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[AdminUserOut]:
    svc = AdminService(db)
    out = await svc.create_admin_user(
        username=body.username, password=body.password, role_id=body.role_id
    )
    return ApiResponse[AdminUserOut](code="1000", message="OK", data=AdminUserOut(**out))


@router.put(
    "/admin-users/{user_id}",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[AdminUserOut],
    summary="Update admin user",
)
async def update_admin_user(
    user_id: int = Path(...),
    body: UpdateAdminUserRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[AdminUserOut]:
    svc = AdminService(db)
    out = await svc.update_admin_user(user_id=user_id, data=body.model_dump(exclude_none=True))
    return ApiResponse[AdminUserOut](code="1000", message="OK", data=AdminUserOut(**out))


@router.delete(
    "/admin-users/{user_id}",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Soft-delete admin user",
)
async def delete_admin_user(
    user_id: int = Path(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    await svc.delete_admin_user(user_id=user_id)
    return ApiResponse[dict](code="1000", message="OK", data={"message": "用户已禁用"})


# --------------------------------------------------------------------------- #
# User management                                                            #
# --------------------------------------------------------------------------- #
@router.get(
    "/users",
    dependencies=[Depends(require_perm("user.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedUserList],
    summary="Paginated user list",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search email / username / nickname"),
) -> ApiResponse[PaginatedUserList]:
    svc = AdminService(db)
    out = await svc.list_users(page=page, page_size=page_size, status=status, q=q)
    return ApiResponse[PaginatedUserList](
        code="1000",
        message="OK",
        data=PaginatedUserList(
            items=[UserOutSafe.from_raw(i) for i in out["items"]],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


@router.get(
    "/users/{user_id}",
    dependencies=[Depends(require_perm("user.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[UserDetailOut],
    summary="C-端用户详情（含订单/材料统计）",
)
async def get_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[UserDetailOut]:
    """C-端用户详情 — 在原 GET /users/{id} 基础上新增 order_count / material_count。
    邮箱/手机号会被脱敏。"""
    svc = AdminService(db)
    out = await svc.get_user_detail(user_id=user_id)
    return ApiResponse[UserDetailOut](
        code="1000",
        message="OK",
        data=UserDetailOut.from_raw(out),
    )


# --------------------------------------------------------------------------- #
# C-端用户管理 (W36: 详情 + 操作)                                              #
# --------------------------------------------------------------------------- #
@router.get(
    "/users/{user_id}/orders",
    dependencies=[Depends(require_perm("user.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedUserOrderList],
    summary="某 C-端用户关联的订单列表（分页）",
)
async def list_user_orders(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ApiResponse[PaginatedUserOrderList]:
    svc = AdminService(db)
    out = await svc.list_user_orders(user_id=user_id, page=page, page_size=page_size)
    # UserOrderItem schema is implicit (Pydantic auto-build from dict via Coercing)
    return ApiResponse[PaginatedUserOrderList](
        code="1000",
        message="OK",
        data=PaginatedUserOrderList(
            items=out["items"],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


@router.post(
    "/users/{user_id}/disable",
    dependencies=[Depends(require_perm("user.disable"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[UserActionResponse],
    summary="禁用 C-端账号（status=disabled）",
)
async def disable_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[UserActionResponse]:
    svc = AdminService(db)
    raw = await svc.disable_user(user_id=user_id)
    return ApiResponse[UserActionResponse](
        code="1000",
        message="账号已禁用",
        data=UserActionResponse(
            user_id=raw["id"], status=raw["status"], message="账号已禁用",
            updated_at=raw["updated_at"],
        ),
    )


@router.post(
    "/users/{user_id}/restore",
    dependencies=[Depends(require_perm("user.disable"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[UserActionResponse],
    summary="恢复 C-端账号（status=active，仅当 status=disabled）",
)
async def restore_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[UserActionResponse]:
    svc = AdminService(db)
    raw = await svc.restore_user(user_id=user_id)
    return ApiResponse[UserActionResponse](
        code="1000",
        message="账号已恢复",
        data=UserActionResponse(
            user_id=raw["id"], status=raw["status"], message="账号已恢复",
            updated_at=raw["updated_at"],
        ),
    )


@router.put(
    "/users/{user_id}",
    dependencies=[Depends(require_perm("user.edit"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[UserOutSafe],
    summary="修改 C-端用户信息（仅 nickname / language_pref / avatar_url）",
)
async def update_user(
    user_id: int = Path(..., ge=1),
    body: UpdateUserRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[UserOutSafe]:
    svc = AdminService(db)
    raw = await svc.update_user(user_id=user_id, data=body.model_dump(exclude_none=True))
    return ApiResponse[UserOutSafe](
        code="1000",
        message="OK",
        data=UserOutSafe.from_raw(raw),
    )


@router.post(
    "/users/{user_id}/reset-password",
    dependencies=[Depends(require_perm("user.reset_password"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[ResetPasswordResponse],
    summary="重置 C-端用户密码（返回一次性明文）",
)
async def reset_user_password(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[ResetPasswordResponse]:
    svc = AdminService(db)
    out = await svc.reset_user_password(user_id=user_id)
    return ApiResponse[ResetPasswordResponse](
        code="1000",
        message="密码已重置，请将新密码告知用户（仅展示一次）",
        data=ResetPasswordResponse(**out),
    )


@router.delete(
    "/users/{user_id}",
    dependencies=[Depends(require_perm("user.disable"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Soft-delete user (sets status=pending_destroy)",
)
async def delete_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    await svc.delete_user(user_id=user_id)
    return ApiResponse[dict](
        code="1000", message="OK", data={"message": "User soft-deleted"}
    )


# --------------------------------------------------------------------------- #
# Order management                                                           #
# --------------------------------------------------------------------------- #
@router.get(
    "/orders",
    dependencies=[Depends(require_perm("order.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedOrderList],
    summary="Paginated order list",
)
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
) -> ApiResponse[PaginatedOrderList]:
    svc = AdminService(db)
    out = await svc.list_orders(
        page=page, page_size=page_size, status=status, user_id=user_id
    )
    return ApiResponse[PaginatedOrderList](
        code="1000",
        message="OK",
        data=PaginatedOrderList(
            items=[OrderOut(**i) for i in out["items"]],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


@router.get(
    "/orders/{order_id}",
    dependencies=[Depends(require_perm("order.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[OrderDetailOut],
    summary="Order detail",
)
async def get_order(
    order_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[OrderDetailOut]:
    svc = AdminService(db)
    out = await svc.get_order(order_id=order_id)
    return ApiResponse[OrderDetailOut](code="1000", message="OK", data=OrderDetailOut(**out))


@router.put(
    "/orders/{order_id}/status",
    dependencies=[Depends(require_perm("order.edit_status"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Update order status (admin override)",
)
async def update_order_status(
    body: UpdateOrderStatusRequest,
    order_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    out = await svc.update_order_status(
        order_id=order_id, new_status=body.status, note=body.note,
        admin=admin,
    )
    return ApiResponse[dict](code="1000", message="OK", data=out)


@router.get(
    "/orders/attention/counts",
    dependencies=[Depends(require_perm("order.view"))],
    response_model=ApiResponse[dict],
    summary="Ops follow-up counters",
)
async def get_order_attention_counts(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    from app.services.order_service import OrderService
    svc = OrderService(db)
    return ApiResponse(code="1000", message="OK", data=await svc.get_attention_counts())


@router.put(
    "/orders/{order_id}/refund",
    dependencies=[Depends(require_perm("order.edit_status"))],
    response_model=ApiResponse[dict],
    summary="Admin refund action: approve | reject | complete | fail",
)
async def update_order_refund(
    order_id: int = Path(..., ge=1),
    action: str = Query(..., pattern="^(approve|reject|complete|fail)$"),
    note: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    if action == "complete" and "payment.refund" not in (admin.permissions or []):
        raise BizException(
            ErrorCode.FORBIDDEN,
            message="payment.refund permission required to complete refund payout",
        )
    svc = AdminService(db)
    out = await svc.update_order_refund(
        order_id, action, admin_id=admin.admin_id, note=note,
    )
    return ApiResponse(code="1000", message="OK", data=out)


@router.put(
    "/orders/{order_id}/portal-submitted",
    dependencies=[Depends(require_perm("order.edit_status"))],
    response_model=ApiResponse[dict],
    summary="Admin marks embassy portal submitted (milestone)",
)
async def admin_mark_portal_submitted(
    order_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    out = await svc.mark_order_portal_submitted(order_id, admin_id=admin.admin_id)
    return ApiResponse(code="1000", message="OK", data=out)


# --------------------------------------------------------------------------- #
# Country config                                                             #
# --------------------------------------------------------------------------- #
@router.get(
    "/config/countries",
    dependencies=[Depends(require_perm("country.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedCountryList],
    summary="List country configurations",
)
async def list_countries(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    enabled: Optional[bool] = Query(None),
) -> ApiResponse[PaginatedCountryList]:
    svc = AdminService(db)
    out = await svc.list_countries(page=page, page_size=page_size, enabled=enabled)
    return ApiResponse[PaginatedCountryList](
        code="1000",
        message="OK",
        data=PaginatedCountryList(
            items=out["items"],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


@router.post(
    "/config/countries",
    dependencies=[Depends(require_perm("country.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[CountryOut],
    status_code=201,
    summary="Create a new country configuration",
)
async def create_country(
    body: CreateCountryRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[CountryOut]:
    svc = AdminService(db)
    out = await svc.create_country(data=body.model_dump())
    return ApiResponse[CountryOut](code="1000", message="OK", data=CountryOut(**out))


@router.put(
    "/config/countries/{country_id}",
    dependencies=[Depends(require_perm("country.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Update country configuration (partial update)",
)
async def update_country(
    body: UpdateCountryRequest,
    country_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    out = await svc.update_country(country_id=country_id, data=body.model_dump())
    return ApiResponse[dict](code="1000", message="OK", data=out)


@router.delete(
    "/config/countries/{country_id}",
    dependencies=[Depends(require_perm("country.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Offline a country (set enabled=False, soft-delete)",
)
async def delete_country(
    country_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    await svc.delete_country(country_id=country_id)
    return ApiResponse[dict](
        code="1000", message="OK", data={"message": "Country disabled"}
    )


@router.post(
    "/config/countries/reorder",
    dependencies=[Depends(require_perm("country.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Bulk-update display_order for the V2 country picker",
)
async def reorder_countries(
    body: ReorderCountriesRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    """Body: ``{ "orders": [{ "id": 1, "display_order": 0 }, ...] }``.

    Writes each (id → display_order) pair in a single transaction and
    returns the refreshed ordered list so the UI can re-render without
    a second round-trip.
    """
    svc = AdminService(db)
    out = await svc.reorder_countries(
        orders=[{"id": item.id, "display_order": item.display_order} for item in body.orders]
    )
    return ApiResponse[dict](code="1000", message="OK", data=out)


@router.post(
    "/config/countries/{country_id}/toggle",
    dependencies=[Depends(require_perm("country.manage"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[CountryOut],
    summary="Toggle the V2 enabled flag for a country",
)
async def toggle_country(
    body: ToggleCountryRequest,
    country_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[CountryOut]:
    """Body: ``{ "enabled": true | false }``.

    Distinct from ``PUT /config/countries/{id}`` because the toggle UX in
    the admin panel is a single click — we don't want operators to also
    have to send the full record just to flip a flag.
    """
    svc = AdminService(db)
    out = await svc.toggle_country(country_id=country_id, enabled=body.enabled)
    return ApiResponse[CountryOut](code="1000", message="OK", data=CountryOut(**out))


# --------------------------------------------------------------------------- #
# Validation rules                                                           #
# --------------------------------------------------------------------------- #
@router.get(
    "/config/validation-rules",
    dependencies=[Depends(require_perm("ai_rules.edit"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[list[ValidationRuleOut]],
    summary="List all AI validation rules",
)
async def get_validation_rules(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[list[ValidationRuleOut]]:
    svc = AdminService(db)
    out = await svc.get_validation_rules()
    return ApiResponse[list[ValidationRuleOut]](
        code="1000", message="OK", data=[ValidationRuleOut(**r) for r in out]
    )


@router.put(
    "/config/validation-rules",
    dependencies=[Depends(require_perm("ai_rules.edit"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[list[ValidationRuleOut]],
    summary="Upsert AI validation rules",
)
async def update_validation_rules(
    body: UpdateValidationRulesRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[list[ValidationRuleOut]]:
    svc = AdminService(db)
    out = await svc.update_validation_rules(rules=body.rules)
    return ApiResponse[list[ValidationRuleOut]](
        code="1000", message="OK", data=[ValidationRuleOut(**r) for r in out]
    )


# --------------------------------------------------------------------------- #
# RPA config                                                                 #
# --------------------------------------------------------------------------- #
@router.get(
    "/config/rpa",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[RpaConfigOut],
    summary="Read RPA rate-limit configuration",
)
async def get_rpa_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[RpaConfigOut]:
    svc = AdminService(db)
    out = svc.get_rpa_config()
    return ApiResponse[RpaConfigOut](code="1000", message="OK", data=RpaConfigOut(**out))


@router.put(
    "/config/rpa",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[RpaConfigOut],
    summary="Update RPA rate-limit configuration",
)
async def update_rpa_config(
    body: UpdateRpaConfigRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[RpaConfigOut]:
    svc = AdminService(db)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    out = await svc.update_rpa_config(updates=updates)
    return ApiResponse[RpaConfigOut](code="1000", message="OK", data=RpaConfigOut(**out))


# --------------------------------------------------------------------------- #
# Audit logs                                                                 #
# --------------------------------------------------------------------------- #
@router.get(
    "/stats/rpa",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[RpaStatsOut],
    summary="Realtime RPA pipeline stats (today visits, queue, 24h failure rate)",
)
async def get_rpa_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[RpaStatsOut]:
    """Snapshot of live RPA scheduler state — visit counter, queue depth,
    and failure ratio for the trailing 24 hours."""
    svc = AdminService(db)
    out = svc.get_rpa_stats()
    return ApiResponse[RpaStatsOut](
        code="1000", message="OK", data=RpaStatsOut(**out)
    )


@router.get(
    "/stats/dashboard",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[DashboardStatsOut],
    summary="Dashboard summary stats (today/week orders, pending, completed, payment rate)",
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[DashboardStatsOut]:
    """Aggregated counts for the admin dashboard — served from an in-process
    TTL cache (60 s) to avoid hammering the DB on every page refresh."""
    svc = AdminService(db)
    out = await svc.get_dashboard_stats()
    return ApiResponse[DashboardStatsOut](
        code="1000", message="OK", data=DashboardStatsOut(**out)
    )


# --------------------------------------------------------------------------- #
# V2 Dashboard — KPI + trend + funnel + top countries + alerts (W37)           #
# --------------------------------------------------------------------------- #
@router.get(
    "/stats/dashboard/summary",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[DashboardSummaryOut],
    summary="顶部 4 张 KPI 卡 (今日订单/营收/新用户/成功率, 含上周对比涨跌)",
)
async def get_dashboard_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[DashboardSummaryOut]:
    """4 张 KPI 大卡 + 同期对比, 60s 内存缓存. 与 /stats/dashboard 共存 (后者是旧的简化版, 待前端切完可下架)."""
    svc = AdminDashboardService(db)
    out = await svc.get_summary()
    return ApiResponse[DashboardSummaryOut](
        code="1000", message="OK", data=DashboardSummaryOut(**out)
    )


@router.get(
    "/stats/dashboard/trend",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[DashboardTrendOut],
    summary="趋势数据 (订单/营收/新用户, 默认 7d, 可选 30d / 90d)",
)
async def get_dashboard_trend(
    metric: str = Query("orders", pattern="^(orders|revenue|users)$"),
    range: str = Query("7d", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[DashboardTrendOut]:
    svc = AdminDashboardService(db)
    out = await svc.get_trend(metric=metric, range_key=range)
    return ApiResponse[DashboardTrendOut](
        code="1000", message="OK", data=DashboardTrendOut(**out)
    )


@router.get(
    "/stats/dashboard/funnel",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[DashboardFunnelOut],
    summary="转化漏斗 (注册 → 选国家 → 创建订单 → 提交 → 支付成功)",
)
async def get_dashboard_funnel(
    range: str = Query("7d", pattern="^(7d|30d)$"),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[DashboardFunnelOut]:
    svc = AdminDashboardService(db)
    out = await svc.get_funnel(range_key=range)
    return ApiResponse[DashboardFunnelOut](
        code="1000", message="OK", data=DashboardFunnelOut(**out)
    )


@router.get(
    "/stats/dashboard/top-countries",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[DashboardTopCountriesOut],
    summary="热门目的地 Top 10 (按订单量)",
)
async def get_dashboard_top_countries(
    range: str = Query("7d", pattern="^(7d|30d)$"),
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[DashboardTopCountriesOut]:
    svc = AdminDashboardService(db)
    out = await svc.get_top_countries(range_key=range, limit=limit)
    return ApiResponse[DashboardTopCountriesOut](
        code="1000", message="OK", data=DashboardTopCountriesOut(**out)
    )


@router.get(
    "/stats/dashboard/alerts",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[DashboardAlertsOut],
    summary="异常告警列表 (RPA 失败率突增 / 某国 24h 零订单 / 待处理积压 / 支付成功率过低)",
)
async def get_dashboard_alerts(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[DashboardAlertsOut]:
    svc = AdminDashboardService(db)
    out = await svc.get_alerts()
    return ApiResponse[DashboardAlertsOut](
        code="1000", message="OK", data=DashboardAlertsOut(**out)
    )


@router.get(
    "/logs",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedAuditLogList],
    summary="Paginated audit log",
)
async def list_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None),
    actor_type: Optional[str] = Query(None),
) -> ApiResponse[PaginatedAuditLogList]:
    svc = AdminService(db)
    out = await svc.list_logs(
        page=page, page_size=page_size, action=action, actor_type=actor_type
    )
    return ApiResponse[PaginatedAuditLogList](
        code="1000",
        message="OK",
        data=PaginatedAuditLogList(
            items=[AuditLogOut(**i) for i in out["items"]],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


# --------------------------------------------------------------------------- #
# Payment flow (资金流)                                                       #
# --------------------------------------------------------------------------- #
@router.get(
    "/payments",
    dependencies=[Depends(require_perm("payment.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedPaymentList],
    summary="Paginated payment flow list (资金流)",
)
async def list_payments(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="none | pending | paid | closed | failed | refunded"),
    refund_status: Optional[str] = Query(None, description="none | pending | approved | completed | rejected | failed"),
) -> ApiResponse[PaginatedPaymentList]:
    svc = AdminService(db)
    out = await svc.list_payments(
        page=page, page_size=page_size, status=status, refund_status=refund_status,
    )
    stats_data = out.get("stats")
    return ApiResponse[PaginatedPaymentList](
        code="1000",
        message="OK",
        data=PaginatedPaymentList(
            items=[PaymentFlowOut(**i) for i in out["items"]],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
            stats=PaymentFlowStats(**stats_data) if stats_data else None,
        ),
    )


# --------------------------------------------------------------------------- #
# Validation rule extensions (W35)                                             #
# --------------------------------------------------------------------------- #
@router.post(
    "/config/validation-rules/test",
    dependencies=[Depends(require_perm("ai_rules.edit"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Test a single validation rule against a sample value",
)
async def test_validation_rule(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    out = await svc.test_validation_rule(
        rule_code=body.get("rule_code") or "",
        sample_value=body.get("sample_value"),
    )
    return ApiResponse[dict](code="1000", message="OK", data=out)


@router.get(
    "/config/validation-rules/{rule_code}/history",
    dependencies=[Depends(require_perm("ai_rules.edit"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[list[AuditLogOut]],
    summary="Modification history for a single validation rule",
)
async def get_validation_rule_history(
    rule_code: str,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[list[AuditLogOut]]:
    svc = AdminService(db)
    items = await svc.get_validation_rule_history(rule_code=rule_code)
    return ApiResponse[list[AuditLogOut]](
        code="1000", message="OK", data=[AuditLogOut(**i) for i in items]
    )


# --------------------------------------------------------------------------- #
# Logs extensions (W35)                                                        #
# --------------------------------------------------------------------------- #
@router.get(
    "/logs/actions",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[list[str]],
    summary="Distinct action list from audit_log (for filter dropdown)",
)
async def list_log_actions(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[list[str]]:
    svc = AdminService(db)
    out = await svc.list_log_actions()
    return ApiResponse[list[str]](code="1000", message="OK", data=out)


@router.get(
    "/logs/{log_id}",
    dependencies=[Depends(require_perm("dashboard.view"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[AuditLogOut],
    summary="Single audit log detail",
)
async def get_log(
    log_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[AuditLogOut]:
    svc = AdminService(db)
    out = await svc.get_log(log_id=log_id)
    return ApiResponse[AuditLogOut](code="1000", message="OK", data=AuditLogOut(**out))


# --------------------------------------------------------------------------- #
# I18n overrides (W35)                                                         #
# --------------------------------------------------------------------------- #
@router.get(
    "/i18n/overrides",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[PaginatedI18nOverrideList],
    summary="List i18n overrides with pagination + filter",
)
async def list_i18n_overrides(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    locale: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="key search"),
) -> ApiResponse[PaginatedI18nOverrideList]:
    svc = AdminService(db)
    out = await svc.list_i18n_overrides(page=page, page_size=page_size, locale=locale, key=q)
    return ApiResponse[PaginatedI18nOverrideList](
        code="1000",
        message="OK",
        data=PaginatedI18nOverrideList(
            items=[I18nOverrideOut(**i) for i in out["items"]],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


@router.post(
    "/i18n/overrides",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[I18nOverrideOut],
    summary="Create i18n override",
)
async def create_i18n_override(
    body: CreateI18nOverrideRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[I18nOverrideOut]:
    svc = AdminService(db)
    out = await svc.create_i18n_override(payload=body.model_dump(), admin_id=admin.admin_id)
    return ApiResponse[I18nOverrideOut](code="1000", message="OK", data=I18nOverrideOut(**out))


@router.put(
    "/i18n/overrides/{override_id}",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[I18nOverrideOut],
    summary="Update i18n override",
)
async def update_i18n_override(
    override_id: int = Path(..., ge=1),
    body: UpdateI18nOverrideRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[I18nOverrideOut]:
    svc = AdminService(db)
    out = await svc.update_i18n_override(
        override_id=override_id, payload=body.model_dump(exclude_none=True), admin_id=admin.admin_id
    )
    return ApiResponse[I18nOverrideOut](code="1000", message="OK", data=I18nOverrideOut(**out))


@router.delete(
    "/i18n/overrides/{override_id}",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Delete i18n override",
)
async def delete_i18n_override(
    override_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    await svc.delete_i18n_override(override_id=override_id, admin_id=admin.admin_id)
    return ApiResponse[dict](code="1000", message="OK", data={"message": "已删除"})


@router.post(
    "/i18n/overrides/import",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Bulk import i18n overrides for a locale",
)
async def import_i18n_overrides(
    body: ImportI18nOverridesRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    out = await svc.import_i18n_overrides(
        locale=body.locale, entries=body.entries or {}, admin_id=admin.admin_id
    )
    return ApiResponse[dict](code="1000", message="OK", data=out)


@router.get(
    "/i18n/overrides/export",
    dependencies=[Depends(require_perm("settings"))],
    # __PERM_DEPENDENCIES_INJECTED__
    response_model=ApiResponse[dict],
    summary="Export all overrides for a locale as JSON dict",
)
async def export_i18n_overrides(
    locale: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token_with_db),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    entries = await svc.export_i18n_overrides(locale=locale)
    return ApiResponse[dict](code="1000", message="OK", data={"locale": locale, "entries": entries})

