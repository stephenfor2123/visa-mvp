"""Platform service-fee pricing — singleton config + promo resolution."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BizException, ErrorCode
from app.models.platform_pricing import PlatformPricing
from app.services.audit import record_audit

_DEFAULTS = {
    "list_price_usd": Decimal("99.90"),
    "promo_price_usd": Decimal("19.90"),
    "currency": "USD",
    "promo_enabled": True,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _usd_to_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


def resolve_pricing(row: PlatformPricing, *, now: Optional[datetime] = None) -> dict[str, Any]:
    """Compute display price from config row."""
    now = now or _utcnow()
    list_price = Decimal(row.list_price_usd)
    promo_price = Decimal(row.promo_price_usd)

    in_window = False
    if row.promo_enabled and row.promo_starts_at and row.promo_ends_at:
        in_window = row.promo_starts_at <= now <= row.promo_ends_at

    is_promo = bool(
        in_window
        and promo_price > 0
        and promo_price < list_price
    )
    display = promo_price if is_promo else list_price

    return {
        "list_price_usd": list_price,
        "promo_price_usd": promo_price,
        "display_price_usd": display,
        "currency": row.currency or "USD",
        "is_promo": is_promo,
        "promo_enabled": bool(row.promo_enabled),
        "promo_starts_at": row.promo_starts_at,
        "promo_ends_at": row.promo_ends_at,
        "display_price_cents": _usd_to_cents(display),
        "list_price_cents": _usd_to_cents(list_price),
    }


class PricingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_row(self) -> PlatformPricing:
        row = await self.db.get(PlatformPricing, 1)
        if row is None:
            row = PlatformPricing(id=1, updated_at=_utcnow(), **_DEFAULTS)
            self.db.add(row)
            await self.db.commit()
            await self.db.refresh(row)
        return row

    async def get_current(self) -> dict[str, Any]:
        row = await self.get_row()
        return resolve_pricing(row)

    async def get_admin(self) -> dict[str, Any]:
        row = await self.get_row()
        resolved = resolve_pricing(row)
        return {
            "id": row.id,
            "list_price_usd": Decimal(row.list_price_usd),
            "promo_price_usd": Decimal(row.promo_price_usd),
            "currency": row.currency,
            "promo_enabled": bool(row.promo_enabled),
            "promo_starts_at": row.promo_starts_at,
            "promo_ends_at": row.promo_ends_at,
            "marketing_note": row.marketing_note,
            "updated_by": row.updated_by,
            "updated_at": row.updated_at,
            "is_promo": resolved["is_promo"],
            "display_price_usd": resolved["display_price_usd"],
        }

    async def update(
        self,
        data: dict[str, Any],
        *,
        admin_id: int = 0,
    ) -> dict[str, Any]:
        list_price = Decimal(str(data["list_price_usd"]))
        promo_price = Decimal(str(data["promo_price_usd"]))
        if promo_price >= list_price:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message="promo_price_usd must be less than list_price_usd",
            )
        starts = data.get("promo_starts_at")
        ends = data.get("promo_ends_at")
        if data.get("promo_enabled") and starts and ends and starts >= ends:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message="promo_starts_at must be before promo_ends_at",
            )

        row = await self.get_row()
        row.list_price_usd = list_price
        row.promo_price_usd = promo_price
        row.currency = (data.get("currency") or "USD").upper()[:8]
        row.promo_enabled = bool(data.get("promo_enabled", True))
        row.promo_starts_at = starts
        row.promo_ends_at = ends
        row.marketing_note = data.get("marketing_note")
        row.updated_by = admin_id or None
        row.updated_at = _utcnow()

        await record_audit(
            self.db,
            actor_type="admin",
            actor_id=admin_id,
            action="admin.pricing.update",
            target_type="platform_pricing",
            target_id=1,
            payload={
                "list_price_usd": str(list_price),
                "promo_price_usd": str(promo_price),
                "promo_enabled": row.promo_enabled,
                "promo_starts_at": starts.isoformat() if starts else None,
                "promo_ends_at": ends.isoformat() if ends else None,
            },
        )
        await self.db.commit()
        await self.db.refresh(row)
        return await self.get_admin()
