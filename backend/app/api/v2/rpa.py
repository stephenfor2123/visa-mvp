"""
RPA API — FastAPI endpoints for RPA submission management.

Endpoints:
  POST /api/v2/rpa/submit         — Trigger RPA submission
  GET  /api/v2/rpa/status/{task_id} — Query task status
  POST /api/v2/rpa/cancel/{task_id} — Cancel a task
  GET  /api/v2/rpa/config          — Query rate-limit config
  PUT  /api/v2/rpa/config          — Update rate-limit config (admin token)
"""
import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.security import get_current_user
from app.models.user import User
from app.services.rpa.rpa_scheduler import RateLimitExceeded, RPASchedulerError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rpa", tags=["rpa"])

# Import singleton from the scheduler module so both modules share one instance
from app.services.rpa.rpa_scheduler import get_scheduler  # noqa: E402


# ------------------------------------------------------------------ #
# Request/Response schemas                                            #
# ------------------------------------------------------------------ #


class RPASubmitRequest(BaseModel):
    """Request body for POST /api/v2/rpa/submit."""
    order_id: str = Field(..., min_length=1, description="Order ID to submit")
    country_code: str = Field(
        ..., min_length=2, max_length=2,
        description="ISO 3166-1 alpha-2 country code (e.g. ID, VN)"
    )
    visa_type: str = Field(
        ...,
        description="Visa type within the country (e.g. visit_visa, e_visa)"
    )
    passport_data: dict[str, Any] = Field(
        ...,
        description="Passport holder data (surname, given_name, dob, passport_no, etc.)"
    )


class RPASubmitResponse(BaseModel):
    """Response for POST /api/v2/rpa/submit."""
    task_id: str
    order_id: str
    status: str
    message: str


class RPATaskStatus(BaseModel):
    """RPA task status response."""
    task_id: str
    order_id: Optional[str] = None
    country_code: Optional[str] = None
    status: str
    progress: float = Field(ge=0.0, le=1.0)
    message: str = ""
    confirmation_no: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RPAConfigResponse(BaseModel):
    """RPA configuration response."""
    rate_limits: dict[str, Any]
    timeouts: dict[str, Any]
    retry: dict[str, Any]
    countries: dict[str, Any]
    mock_mode: bool


class RPAConfigUpdateRequest(BaseModel):
    """Request body for PUT /api/v2/rpa/config."""
    rate_limits: Optional[dict[str, Any]] = None
    timeouts: Optional[dict[str, Any]] = None
    retry: Optional[dict[str, Any]] = None
    mock_mode: Optional[bool] = None


class ApiResponse(BaseModel, generic_field=True):
    """Standard API response envelope."""
    code: str = "1000"
    message: str = "OK"
    data: Any = None


# ------------------------------------------------------------------ #
# Endpoints                                                            #
# ------------------------------------------------------------------ #

@router.post(
    "/submit",
    response_model=ApiResponse[RPASubmitResponse],
    summary="Submit a visa application via RPA",
    description="Creates a new RPA task to submit a visa application for the given order.",
)
async def rpa_submit(
    req: RPASubmitRequest,
    current_user: User = Depends(get_current_user),
    x_forwarded_for: Optional[str] = Header(None),
) -> dict[str, Any]:
    """
    POST /api/v2/rpa/submit

    Trigger an RPA submission for a visa application.

    Requires JWT bearer authentication.
    """
    scheduler = get_scheduler()

    try:
        task_id = scheduler.submit_visa_application(
            order_id=req.order_id,
            country_code=req.country_code,
            visa_type=req.visa_type,
            user_id=str(current_user.id),
            ip_address=x_forwarded_for,
        )
        status_info = scheduler.get_task_status(task_id, owner_user_id=str(current_user.id))

        return {
            "code": "1000",
            "message": "RPA task created",
            "data": {
                "task_id": task_id,
                "order_id": req.order_id,
                "status": status_info["status"],
                "message": status_info["message"],
            }
        }

    except RateLimitExceeded as exc:
        logger.warning("Rate limit exceeded: %s", exc)
        raise BizException(
            ErrorCode.RATE_LIMIT,
            message=str(exc),
        )

    except RPASchedulerError as exc:
        logger.error("RPA scheduler error: %s", exc)
        raise BizException(
            ErrorCode.ORDER_INVALID_STATE,
            message=str(exc),
        )


@router.get(
    "/status/{task_id}",
    response_model=ApiResponse[RPATaskStatus],
    summary="Get RPA task status",
    description="Query the current status of an RPA submission task. Requires JWT auth; returns 404 if task belongs to another user (IDOR prevention).",
)
async def rpa_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    GET /api/v2/rpa/status/{task_id}

    Returns detailed status of an RPA task including progress and confirmation.
    Only returns data if the task belongs to the authenticated user.
    """
    scheduler = get_scheduler()
    status_info = scheduler.get_task_status(task_id, owner_user_id=str(current_user.id))

    if status_info.get("status") == "not_found":
        raise BizException(ErrorCode.NOT_FOUND, message=f"Task {task_id} not found")

    return {
        "code": "1000",
        "message": "OK",
        "data": status_info,
    }


@router.post(
    "/cancel/{task_id}",
    response_model=ApiResponse[RPATaskStatus],
    summary="Cancel an RPA task",
    description="Cancel a pending or in-progress RPA submission task. Requires JWT auth.",
)
async def rpa_cancel(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    POST /api/v2/rpa/cancel/{task_id}

    Cancel a pending or in-progress RPA task. Only the task owner can cancel.
    """
    scheduler = get_scheduler()
    status_info = scheduler.cancel_task(task_id, owner_user_id=str(current_user.id))

    if status_info.get("status") == "not_found":
        raise BizException(ErrorCode.NOT_FOUND, message=f"Task {task_id} not found")

    return {
        "code": "1000",
        "message": f"Task cancelled (status: {status_info['status']})",
        "data": status_info,
    }


@router.get(
    "/config",
    response_model=ApiResponse[RPAConfigResponse],
    summary="Get RPA configuration",
    description="Query current RPA rate limits, timeouts, and retry settings.",
)
async def rpa_get_config() -> dict[str, Any]:
    """
    GET /api/v2/rpa/config

    Returns the current RPA configuration (safe subset, no secrets).
    """
    scheduler = get_scheduler()
    config = scheduler.get_config()

    return {
        "code": "1000",
        "message": "OK",
        "data": config,
    }


@router.put(
    "/config",
    response_model=ApiResponse[RPAConfigResponse],
    summary="Update RPA configuration",
    description="Update RPA rate limits and timeout settings. Requires admin token.",
)
async def rpa_update_config(
    req: RPAConfigUpdateRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """
    PUT /api/v2/rpa/config

    Update RPA configuration (runtime, not persisted to file).
    Requires X-Admin-Token header matching the system API key.
    """
    settings = get_settings()
    admin_token = x_admin_token

    if not admin_token:
        raise BizException(
            ErrorCode.UNAUTHORIZED,
            message="X-Admin-Token header is required",
        )

    if admin_token != settings.system_api_key:
        raise BizException(
            ErrorCode.FORBIDDEN,
            message="Invalid admin token",
        )

    scheduler = get_scheduler()
    updates = req.model_dump(exclude_none=True)
    config = scheduler.update_config(updates)

    logger.info("RPA config updated by admin: %s", list(updates.keys()))

    return {
        "code": "1000",
        "message": "Configuration updated",
        "data": config,
    }


@router.get(
    "/tasks",
    response_model=ApiResponse[list[RPATaskStatus]],
    summary="List RPA tasks",
    description="List tasks for the authenticated user. Requires JWT auth.",
)
async def rpa_list_tasks(
    order_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    GET /api/v2/rpa/tasks

    List tasks for the authenticated user, optionally filtered.
    Only returns tasks owned by the current user.
    """
    scheduler = get_scheduler()

    from app.services.rpa.rpa_scheduler import TaskStatus
    status_enum = TaskStatus(status_filter) if status_filter else None

    tasks = scheduler.list_tasks(
        order_id=order_id,
        user_id=str(current_user.id),
        status=status_enum,
    )

    return {
        "code": "1000",
        "message": f"Found {len(tasks)} task(s)",
        "data": tasks,
    }