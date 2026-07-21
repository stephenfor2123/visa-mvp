"""Platform service-fee pricing — global + per country/visa_type."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BizException, ErrorCode
from app.models.destination import VisaDestination
from app.models.destination_pricing import VISA_TYPE_ALL, DestinationPricing
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


def _norm_country(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return str(code).strip().upper() or None


def _norm_visa(visa_type: Optional[str]) -> Optional[str]:
    if not visa_type:
        return None
    v = str(visa_type).strip().lower()
    return v or None


def resolve_pricing_fields(
    *,
    list_price_usd: Decimal,
    promo_price_usd: Decimal,
    currency: str = "USD",
    promo_enabled: bool = True,
    promo_starts_at: Optional[datetime] = None,
    promo_ends_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Compute display price from raw fee fields."""
    now = now or _utcnow()
    list_price = Decimal(list_price_usd)
    promo_price = Decimal(promo_price_usd)

    in_window = False
    if promo_enabled and promo_starts_at and promo_ends_at:
        in_window = promo_starts_at <= now <= promo_ends_at

    is_promo = bool(in_window and promo_price > 0 and promo_price < list_price)
    display = promo_price if is_promo else list_price

    return {
        "list_price_usd": list_price,
        "promo_price_usd": promo_price,
        "display_price_usd": display,
        "currency": currency or "USD",
        "is_promo": is_promo,
        "promo_enabled": bool(promo_enabled),
        "promo_starts_at": promo_starts_at,
        "promo_ends_at": promo_ends_at,
        "display_price_cents": _usd_to_cents(display),
        "list_price_cents": _usd_to_cents(list_price),
    }


def resolve_pricing(row: PlatformPricing, *, now: Optional[datetime] = None) -> dict[str, Any]:
    """Compute display price from global config row."""
    return resolve_pricing_fields(
        list_price_usd=Decimal(row.list_price_usd),
        promo_price_usd=Decimal(row.promo_price_usd),
        currency=row.currency or "USD",
        promo_enabled=bool(row.promo_enabled),
        promo_starts_at=row.promo_starts_at,
        promo_ends_at=row.promo_ends_at,
        now=now,
    )


def resolve_destination_row(
    row: DestinationPricing, *, now: Optional[datetime] = None
) -> dict[str, Any]:
    return resolve_pricing_fields(
        list_price_usd=Decimal(row.list_price_usd),
        promo_price_usd=Decimal(row.promo_price_usd),
        currency=row.currency or "USD",
        promo_enabled=bool(row.promo_enabled),
        promo_starts_at=row.promo_starts_at,
        promo_ends_at=row.promo_ends_at,
        now=now,
    )


def _country_name_from_i18n(raw: Optional[str], lang: str = "zh-CN") -> Optional[str]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data.get(lang) or data.get("zh-CN") or data.get("en") or next(iter(data.values()), None)
    except Exception:
        return raw
    return None


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

    async def get_current(
        self,
        *,
        country_code: Optional[str] = None,
        visa_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resolve fee: exact destination → country * → global."""
        cc = _norm_country(country_code)
        vt = _norm_visa(visa_type)

        if cc and vt:
            row = await self.db.scalar(
                select(DestinationPricing).where(
                    DestinationPricing.country_code == cc,
                    DestinationPricing.visa_type == vt,
                )
            )
            if row is not None:
                out = resolve_destination_row(row)
                out["country_code"] = cc
                out["visa_type"] = vt
                out["source"] = "destination_exact"
                return out

        if cc:
            row = await self.db.scalar(
                select(DestinationPricing).where(
                    DestinationPricing.country_code == cc,
                    DestinationPricing.visa_type == VISA_TYPE_ALL,
                )
            )
            if row is not None:
                out = resolve_destination_row(row)
                out["country_code"] = cc
                out["visa_type"] = vt
                out["source"] = "destination_country"
                return out

        global_row = await self.get_row()
        out = resolve_pricing(global_row)
        out["country_code"] = cc
        out["visa_type"] = vt
        out["source"] = "global"
        return out

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

    def _validate_prices(self, data: dict[str, Any]) -> tuple[Decimal, Decimal]:
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
        return list_price, promo_price

    async def update(
        self,
        data: dict[str, Any],
        *,
        admin_id: int = 0,
    ) -> dict[str, Any]:
        list_price, promo_price = self._validate_prices(data)
        starts = data.get("promo_starts_at")
        ends = data.get("promo_ends_at")

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

    async def list_destination_pricing(self) -> dict[str, Any]:
        """Global config + one row per (enabled destination × visa_type)."""
        global_admin = await self.get_admin()
        dests = (
            await self.db.execute(
                select(VisaDestination)
                .where(VisaDestination.enabled == True)  # noqa: E712
                .order_by(VisaDestination.display_order, VisaDestination.country_code)
            )
        ).scalars().all()

        existing = (
            await self.db.execute(select(DestinationPricing))
        ).scalars().all()
        by_key = {(r.country_code.upper(), r.visa_type.lower()): r for r in existing}

        items: list[dict[str, Any]] = []
        for dest in dests:
            cc = (dest.country_code or "").upper()
            try:
                types = json.loads(dest.visa_types or "[]")
            except Exception:
                types = []
            if not isinstance(types, list) or not types:
                types = ["tourism"]
            name = _country_name_from_i18n(dest.country_name_i18n)
            for vt_raw in types:
                vt = str(vt_raw or "tourism").strip().lower() or "tourism"
                row = by_key.get((cc, vt))
                if row is None:
                    resolved = resolve_pricing_fields(
                        list_price_usd=Decimal(str(global_admin["list_price_usd"])),
                        promo_price_usd=Decimal(str(global_admin["promo_price_usd"])),
                        currency=global_admin.get("currency") or "USD",
                        promo_enabled=bool(global_admin.get("promo_enabled", True)),
                        promo_starts_at=global_admin.get("promo_starts_at"),
                        promo_ends_at=global_admin.get("promo_ends_at"),
                    )
                    items.append(
                        {
                            "id": None,
                            "country_code": cc,
                            "country_name": name,
                            "visa_type": vt,
                            "list_price_usd": resolved["list_price_usd"],
                            "promo_price_usd": resolved["promo_price_usd"],
                            "currency": resolved["currency"],
                            "promo_enabled": resolved["promo_enabled"],
                            "promo_starts_at": resolved["promo_starts_at"],
                            "promo_ends_at": resolved["promo_ends_at"],
                            "marketing_note": global_admin.get("marketing_note"),
                            "updated_by": None,
                            "updated_at": None,
                            "is_promo": resolved["is_promo"],
                            "display_price_usd": resolved["display_price_usd"],
                            "inherited": True,
                        }
                    )
                else:
                    resolved = resolve_destination_row(row)
                    items.append(
                        {
                            "id": row.id,
                            "country_code": cc,
                            "country_name": name,
                            "visa_type": vt,
                            "list_price_usd": Decimal(row.list_price_usd),
                            "promo_price_usd": Decimal(row.promo_price_usd),
                            "currency": row.currency or "USD",
                            "promo_enabled": bool(row.promo_enabled),
                            "promo_starts_at": row.promo_starts_at,
                            "promo_ends_at": row.promo_ends_at,
                            "marketing_note": row.marketing_note,
                            "updated_by": row.updated_by,
                            "updated_at": row.updated_at,
                            "is_promo": resolved["is_promo"],
                            "display_price_usd": resolved["display_price_usd"],
                            "inherited": False,
                        }
                    )

        return {"global_pricing": global_admin, "items": items}

    async def upsert_destination_pricing(
        self,
        data: dict[str, Any],
        *,
        admin_id: int = 0,
    ) -> dict[str, Any]:
        list_price, promo_price = self._validate_prices(data)
        cc = _norm_country(data.get("country_code"))
        vt = _norm_visa(data.get("visa_type"))
        if not cc or not vt:
            raise BizException(
                ErrorCode.INVALID_PARAMS,
                message="country_code and visa_type are required",
            )
        if vt == VISA_TYPE_ALL:
            # allow explicit '*'
            pass

        starts = data.get("promo_starts_at")
        ends = data.get("promo_ends_at")

        row = await self.db.scalar(
            select(DestinationPricing).where(
                DestinationPricing.country_code == cc,
                DestinationPricing.visa_type == vt,
            )
        )
        created = False
        if row is None:
            row = DestinationPricing(country_code=cc, visa_type=vt)
            self.db.add(row)
            created = True

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
            action="admin.destination_pricing.upsert",
            target_type="destination_pricing",
            target_id=None,
            payload={
                "country_code": cc,
                "visa_type": vt,
                "list_price_usd": str(list_price),
                "promo_price_usd": str(promo_price),
                "created": created,
            },
        )
        await self.db.commit()
        await self.db.refresh(row)

        dest = await self.db.scalar(
            select(VisaDestination).where(VisaDestination.country_code == cc)
        )
        resolved = resolve_destination_row(row)
        return {
            "id": row.id,
            "country_code": cc,
            "country_name": _country_name_from_i18n(
                dest.country_name_i18n if dest else None
            ),
            "visa_type": vt,
            "list_price_usd": Decimal(row.list_price_usd),
            "promo_price_usd": Decimal(row.promo_price_usd),
            "currency": row.currency or "USD",
            "promo_enabled": bool(row.promo_enabled),
            "promo_starts_at": row.promo_starts_at,
            "promo_ends_at": row.promo_ends_at,
            "marketing_note": row.marketing_note,
            "updated_by": row.updated_by,
            "updated_at": row.updated_at,
            "is_promo": resolved["is_promo"],
            "display_price_usd": resolved["display_price_usd"],
            "inherited": False,
        }
