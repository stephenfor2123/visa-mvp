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

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.middleware.admin_auth import verify_admin_token
from app.schemas.admin import (
    AdminLoginRequest,
    AdminTokenData,
    AdminTokenOut,
    CountryOut,
    CreateCountryRequest,
    PaginatedAuditLogList,
    PaginatedOrderList,
    PaginatedUserList,
    RpaConfigOut,
    RpaStatsOut,
    UpdateCountryRequest,
    UpdateOrderStatusRequest,
    UpdateRpaConfigRequest,
    UpdateValidationRulesRequest,
    ValidationRuleOut,
    AuditLogOut,
    DashboardStatsOut,
    OrderDetailOut,
    OrderOut,
    UserOut,
    UserOutSafe,
)
from app.schemas.admin import (
    AdminLoginRequest,
    AdminTokenData,
    AdminTokenOut,
    AuditLogOut,
    CountryOut,
    CreateCountryRequest,
    PaginatedAuditLogList,
    PaginatedCountryList,
    PaginatedOrderList,
    PaginatedUserList,
    RpaConfigOut,
    UpdateCountryRequest,
    UpdateOrderStatusRequest,
    UpdateRpaConfigRequest,
    UpdateValidationRulesRequest,
    ValidationRuleOut,
    OrderDetailOut,
    OrderOut,
    UserOut,
    UserOutSafe,
)
from app.schemas.common import ApiResponse
from app.services.admin_service import AdminService


# Module-level router (W14-3 left this declaration missing, breaking import).
router = APIRouter(prefix="/admin", tags=["admin"])


# --------------------------------------------------------------------------- #
# Auth                                                                       #
# --------------------------------------------------------------------------- #
@router.post(
    "/login",
    response_model=ApiResponse[AdminTokenOut],
    summary="Admin login (independent from C-user auth)",
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
# User management                                                            #
# --------------------------------------------------------------------------- #
@router.get(
    "/users",
    response_model=ApiResponse[PaginatedUserList],
    summary="Paginated user list",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
) -> ApiResponse[PaginatedUserList]:
    svc = AdminService(db)
    out = await svc.list_users(page=page, page_size=page_size, status=status)
    return ApiResponse[PaginatedUserList](
        code="1000",
        message="OK",
        data=PaginatedUserList(
            items=[UserOutSafe.from_user_out(UserOut(**i)) for i in out["items"]],
            page=out["page"],
            page_size=out["page_size"],
            total=out["total"],
            total_pages=out["total_pages"],
        ),
    )


@router.get(
    "/users/{user_id}",
    response_model=ApiResponse[UserOutSafe],
    summary="User detail",
)
async def get_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[UserOutSafe]:
    svc = AdminService(db)
    out = await svc.get_user(user_id=user_id)
    return ApiResponse[UserOutSafe](
        code="1000",
        message="OK",
        data=UserOutSafe.from_user_out(UserOut(**out)),
    )


@router.delete(
    "/users/{user_id}",
    response_model=ApiResponse[dict],
    summary="Soft-delete user (sets status=pending_destroy)",
)
async def delete_user(
    user_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
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
    response_model=ApiResponse[PaginatedOrderList],
    summary="Paginated order list",
)
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
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
    response_model=ApiResponse[OrderDetailOut],
    summary="Order detail",
)
async def get_order(
    order_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[OrderDetailOut]:
    svc = AdminService(db)
    out = await svc.get_order(order_id=order_id)
    return ApiResponse[OrderDetailOut](code="1000", message="OK", data=OrderDetailOut(**out))


@router.put(
    "/orders/{order_id}/status",
    response_model=ApiResponse[dict],
    summary="Update order status (admin override)",
)
async def update_order_status(
    body: UpdateOrderStatusRequest,
    order_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    out = await svc.update_order_status(
        order_id=order_id, new_status=body.status, note=body.note
    )
    return ApiResponse[dict](code="1000", message="OK", data=out)


# --------------------------------------------------------------------------- #
# Country config                                                             #
# --------------------------------------------------------------------------- #
@router.get(
    "/config/countries",
    response_model=ApiResponse[PaginatedCountryList],
    summary="List country configurations",
)
async def list_countries(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
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
    response_model=ApiResponse[CountryOut],
    status_code=201,
    summary="Create a new country configuration",
)
async def create_country(
    body: CreateCountryRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[CountryOut]:
    svc = AdminService(db)
    out = await svc.create_country(data=body.model_dump())
    return ApiResponse[CountryOut](code="1000", message="OK", data=CountryOut(**out))


@router.put(
    "/config/countries/{country_id}",
    response_model=ApiResponse[dict],
    summary="Update country configuration (partial update)",
)
async def update_country(
    body: UpdateCountryRequest,
    country_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    out = await svc.update_country(country_id=country_id, data=body.model_dump())
    return ApiResponse[dict](code="1000", message="OK", data=out)


@router.delete(
    "/config/countries/{country_id}",
    response_model=ApiResponse[dict],
    summary="Offline a country (set enabled=False)",
)
async def delete_country(
    country_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[dict]:
    svc = AdminService(db)
    await svc.delete_country(country_id=country_id)
    return ApiResponse[dict](
        code="1000", message="OK", data={"message": "Country disabled"}
    )


# --------------------------------------------------------------------------- #
# Validation rules                                                           #
# --------------------------------------------------------------------------- #
@router.get(
    "/config/validation-rules",
    response_model=ApiResponse[list[ValidationRuleOut]],
    summary="List all AI validation rules",
)
async def get_validation_rules(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[list[ValidationRuleOut]]:
    svc = AdminService(db)
    out = await svc.get_validation_rules()
    return ApiResponse[list[ValidationRuleOut]](
        code="1000", message="OK", data=[ValidationRuleOut(**r) for r in out]
    )


@router.put(
    "/config/validation-rules",
    response_model=ApiResponse[list[ValidationRuleOut]],
    summary="Upsert AI validation rules",
)
async def update_validation_rules(
    body: UpdateValidationRulesRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
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
    response_model=ApiResponse[RpaConfigOut],
    summary="Read RPA rate-limit configuration",
)
async def get_rpa_config(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[RpaConfigOut]:
    svc = AdminService(db)
    out = svc.get_rpa_config()
    return ApiResponse[RpaConfigOut](code="1000", message="OK", data=RpaConfigOut(**out))


@router.put(
    "/config/rpa",
    response_model=ApiResponse[RpaConfigOut],
    summary="Update RPA rate-limit configuration",
)
async def update_rpa_config(
    body: UpdateRpaConfigRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[RpaConfigOut]:
    svc = AdminService(db)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    out = svc.update_rpa_config(updates=updates)
    return ApiResponse[RpaConfigOut](code="1000", message="OK", data=RpaConfigOut(**out))


# --------------------------------------------------------------------------- #
# Audit logs                                                                 #
# --------------------------------------------------------------------------- #
@router.get(
    "/stats/rpa",
    response_model=ApiResponse[RpaStatsOut],
    summary="Realtime RPA pipeline stats (today visits, queue, 24h failure rate)",
)
async def get_rpa_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
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
    response_model=ApiResponse[DashboardStatsOut],
    summary="Dashboard summary stats (today/week orders, pending, completed, payment rate)",
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: AdminTokenData = Depends(verify_admin_token),
) -> ApiResponse[DashboardStatsOut]:
    """Aggregated counts for the admin dashboard — served from an in-process
    TTL cache (60 s) to avoid hammering the DB on every page refresh."""
    svc = AdminService(db)
    out = svc.get_dashboard_stats()
    return ApiResponse[DashboardStatsOut](
        code="1000", message="OK", data=DashboardStatsOut(**out)
    )


@router.get(
    "/logs",
    response_model=ApiResponse[PaginatedAuditLogList],
    summary="Paginated audit log",
)
async def list_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: AdminTokenData = Depends(verify_admin_token),
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
