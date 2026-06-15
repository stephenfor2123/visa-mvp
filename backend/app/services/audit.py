"""Audit-log helper — fire-and-forget but always returns the row id."""
import json
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog


_log = get_logger()


async def record_audit(
    db: AsyncSession,
    *,
    actor_type: str,
    action: str,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    payload: Optional[dict[str, Any]] = None,
) -> int:
    """Insert an audit row. Caller is responsible for committing the session."""
    row = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    db.add(row)
    await db.flush()
    _log.info(
        "audit actor={}:{} action={} target={}:{}",
        actor_type,
        actor_id,
        action,
        target_type,
        target_id,
    )
    return row.id
