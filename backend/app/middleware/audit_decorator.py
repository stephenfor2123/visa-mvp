"""
@audit_log decorator — fire-and-forget audit trail for admin write operations.

Usage:
    @router.delete("/users/{user_id}")
    @audit_log(action="admin.user.delete", target_type="user",
               admin_kw="admin", db_kw="db")
    async def delete_user(user_id: int, db: AsyncSession, admin: AdminTokenData):
        ...

The decorator intercepts the response, extracts admin/db from kwargs,
and fires an audit record asynchronously.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.admin_auth import AdminTokenData
from app.models.audit_log import AuditLog


async def _write_audit(
    admin: AdminTokenData,
    db: AsyncSession,
    action: str,
    target_type: str,
    target_id: Optional[int],
    ip: str,
    method: str,
    path: str,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Write one audit row and commit its session."""
    payload = {"ip": ip, "method": method, "path": path}
    if extra:
        payload.update(extra)

    row = AuditLog(
        actor_type="admin",
        actor_id=admin.admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=json.dumps(payload, ensure_ascii=False),
    )
    db.add(row)
    await db.commit()


def audit_log(
    action: str,
    target_type: str,
    *,
    admin_kw: str = "admin",
    db_kw: str = "db",
    target_id_kw: Optional[str] = None,
    extra_kw: Optional[str] = None,
):
    """
    Fire-and-forget audit decorator for admin write endpoints.

    After the wrapped endpoint returns successfully, extracts admin/db from
    the function's kwargs and emits one AuditLog row asynchronously.

    Parameters
    ----------
    action:
        Dot-separated action name, e.g. "admin.user.delete".
    target_type:
        Entity type being acted on: "user" | "order" | "country" | etc.
    admin_kw:
        Name of the keyword argument that carries the AdminTokenData.
    db_kw:
        Name of the keyword argument that carries the AsyncSession.
    target_id_kw:
        Name of a kwarg whose value is the integer target_id.
        If omitted the audit row's target_id is None.
    extra_kw:
        Name of a kwarg whose value is a dict of extra payload fields.
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            response = await func(*args, **kwargs)

            try:
                admin: AdminTokenData = kwargs[admin_kw]
                db: AsyncSession = kwargs[db_kw]
            except KeyError:
                # Missing deps — skip audit silently (won't happen for properly
                # decorated endpoints).
                return response

            # Extract target_id if a kwarg name was given
            target_id: Optional[int] = None
            if target_id_kw and target_id_kw in kwargs:
                target_id = kwargs[target_id_kw]

            # Extract extra payload dict if a kwarg name was given
            extra: Optional[dict[str, Any]] = None
            if extra_kw and extra_kw in kwargs:
                extra = kwargs[extra_kw]

            # Derive client IP
            # Try to get Request from kwargs (some endpoints receive it)
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                # Scan positional args for a Request
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            ip = "unknown"
            if request is not None:
                ip = (
                    request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                    or request.headers.get("x-real-ip")
                    or (request.client.host if request.client else None)
                    or "unknown"
                )
                path = request.url.path
                method = request.method
            else:
                method = "UNKNOWN"
                path = "/"

            # Fire-and-forget — do not block the response
            asyncio.create_task(
                _write_audit(
                    admin=admin,
                    db=db,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    ip=ip,
                    method=method,
                    path=path,
                    extra=extra,
                )
            )
            return response

        return wrapper

    return decorator