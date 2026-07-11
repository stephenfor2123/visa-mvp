"""
Admin authentication middleware — bearer JWT with role=admin.

Independent from the C-user JWT (different secret + claims structure).
All /admin/* endpoints are protected by verify_admin_token, optionally
followed by require_perm for fine-grained perm checks.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.permissions import all_perm_codes
from app.models.admin_role import AdminRole
from app.models.admin_user import AdminUser
from app.schemas.admin import AdminTokenData


_admin_bearer = HTTPBearer(auto_error=False, description="Admin JWT access token")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_admin_token(
    admin_id: int,
    username: str,
    settings: Optional[Any] = None,
    permissions: Optional[list[str]] = None,
) -> tuple[str, datetime]:
    """Create an admin JWT with role=admin.

    `permissions` 嵌入 token 载荷,前端拿到后用于菜单显隐与按钮权限校验;
    后端鉴权以 DB 为准(见 verify_admin_token),token 内嵌的 perms 只是一个
    便于前端快速判断的 hint。
    """
    import secrets

    settings = settings or get_settings()
    now = _now_utc()
    exp = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(admin_id),
        "type": "admin_access",
        "role": "admin",
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
    }
    if permissions:
        payload["perms"] = list(permissions)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, exp


def decode_admin_token(token: str, settings: Optional[Any] = None) -> dict[str, Any]:
    """Decode and validate an admin token. Raises BizException on failure."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise BizException(ErrorCode.UNAUTHORIZED, message="Invalid admin token")

    if payload.get("role") != "admin":
        raise BizException(ErrorCode.FORBIDDEN, message="Not an admin token")

    exp = payload.get("exp")
    if exp is not None and datetime.fromtimestamp(int(exp), tz=timezone.utc) < _now_utc():
        raise BizException(ErrorCode.UNAUTHORIZED, message="Admin token expired")

    return payload


async def _resolve_admin_data(
    payload: dict[str, Any],
    db: Optional[AsyncSession],
) -> AdminTokenData:
    """根据 token payload 拿权威 AdminTokenData(查 DB 拿 permissions)。"""
    admin_id = int(payload["sub"])

    # env fallback 超管 (id=0) — 全权限直接放行
    if admin_id == 0:
        return AdminTokenData(
            admin_id=0,
            username=payload.get("username", "admin"),
            role="admin",
            role_code="super_admin",
            permissions=all_perm_codes(),
        )

    # DB 账号 — 必须查到最新 permissions(避免角色被改后旧 token 仍生效)
    if db is None:
        # 没有 db session 时降级使用 token hint
        return AdminTokenData(
            admin_id=admin_id,
            username=payload.get("username", "admin"),
            role=payload.get("role", "admin"),
            permissions=payload.get("perms", []),
        )

    user = (
        await db.execute(
            select(AdminUser)
            .options(selectinload(AdminUser.role))
            .where(AdminUser.id == admin_id, AdminUser.is_active == True)  # noqa: E712
        )
    ).scalar_one_or_none()
    if user is None:
        raise BizException(ErrorCode.UNAUTHORIZED, message="Admin not found or disabled")
    role = user.role
    return AdminTokenData(
        admin_id=admin_id,
        username=user.username,
        role=role.code if role else "admin",
        role_code=role.code if role else None,
        permissions=list(role.permissions) if role and role.permissions else [],
    )


async def verify_admin_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_admin_bearer),
) -> AdminTokenData:
    """FastAPI dependency — resolve admin bearer token to AdminTokenData。

    仅做 token 校验 + 返回 token 内嵌的 username/role。
    **不会查 DB** — 这是为了不让 admin 列表等读接口多走一次 SELECT。
    需要真实 permissions 时请用 verify_admin_token_with_db 或 require_perm。
    """
    if credentials is None or not credentials.credentials:
        raise BizException(
            ErrorCode.UNAUTHORIZED, message="Missing admin bearer token"
        )

    payload = decode_admin_token(credentials.credentials)
    try:
        admin_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise BizException(ErrorCode.UNAUTHORIZED, message="Bad admin token subject")

    return AdminTokenData(
        admin_id=admin_id,
        username=payload.get("username", "admin"),
        role=payload.get("role", "admin"),
        permissions=payload.get("perms", []),
    )


async def verify_admin_token_with_db(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_admin_bearer),
    db: AsyncSession = Depends(get_db),
) -> AdminTokenData:
    """带显式 db session 的版本 — 配合 require_perm 使用以保证 permissions 实时。"""
    if credentials is None or not credentials.credentials:
        raise BizException(
            ErrorCode.UNAUTHORIZED, message="Missing admin bearer token"
        )

    payload = decode_admin_token(credentials.credentials)
    return await _resolve_admin_data(payload, db)


def require_perm(*perm_codes: str):
    """FastAPI dependency factory — 校验当前 admin 是否拥有指定 perm。

    用法:
        @router.post("/xxx", dependencies=[Depends(require_perm("order.edit_status"))])
        async def xxx(...): ...

    super_admin 自动通过(全权限)。
    """
    from fastapi import Depends

    async def _checker(
        admin: AdminTokenData = Depends(verify_admin_token_with_db),
    ) -> AdminTokenData:
        if admin.role_code == "super_admin":
            return admin
        for code in perm_codes:
            if code not in admin.permissions:
                raise BizException(
                    ErrorCode.FORBIDDEN,
                    message=f"权限不足:需要 {code}",
                    data={"required_perm": code, "missing": True},
                )
        return admin

    return _checker