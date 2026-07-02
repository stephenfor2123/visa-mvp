"""/api/v2/destinations — 国家列表(V2 范围 = 美国 V2 启用)"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.schemas.common import ApiResponse
from app.models.destination import VisaDestination

logger = get_logger()

router = APIRouter(tags=["destinations"])


class DestinationOut(BaseModel):
    id: int
    country_code: str
    country_name: str
    visa_types: List[str]
    image_url: Optional[str]
    enabled: bool
    # Atlys-style (W28): price / validity / processing time / precise ETA
    visa_fee_usd: Optional[int] = None        # USD cents — display only
    valid_days: Optional[int] = None          # visa validity in days
    process_days: Optional[int] = None        # typical processing days
    eta_iso: Optional[str] = None             # ISO-8601 UTC of "Guaranteed Visa on …"

    model_config = {"from_attributes": True}


def _format_valid_label(days: int) -> str:
    """Best-effort human label for visa validity."""
    if days <= 0:
        return ""
    if days % 365 == 0:
        years = days // 365
        return f"{years} YEAR" + ("S" if years > 1 else "")
    if days % 30 == 0:
        months = days // 30
        return f"{months} MONTH" + ("S" if months > 1 else "")
    return f"{days} DAYS"


# W45 fix: hard-coded ISO 3166-1 alpha-2 → English short name fallback.
# Used when the DB's country_name_i18n is missing a locale (e.g. seed_schengen_26
# wrote a plain "Austria" string for the 'en' slot only — English works, but
# asking for lang=zh-CN/id-ID/vi-VN used to fall back to the country code "AT",
# which is ugly on the card title). Keep this table small (≤ 30 entries for the
# V2 destinations); once we re-seed, the i18n column will be the source of truth.
_COUNTRY_NAME_EN_FALLBACK = {
    "US": "United States",
    "AU": "Australia",
    "GB": "United Kingdom",
    "JP": "Japan",
    "CA": "Canada",
    "SG": "Singapore",
    "NZ": "New Zealand",
    "DE": "Germany",
    "FR": "France",
    "AT": "Austria",
    "BE": "Belgium",
    "HR": "Croatia",
    "CZ": "Czechia",
    "DK": "Denmark",
    "EE": "Estonia",
    "FI": "Finland",
    "GR": "Greece",
    "HU": "Hungary",
    "IS": "Iceland",
    "IT": "Italy",
    "LV": "Latvia",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "MT": "Malta",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "ES": "Spain",
    "SE": "Sweden",
    "SCHENGEN": "Schengen (any of 26 members)",
}


def _compute_eta_iso(process_days: Optional[int]) -> Optional[str]:
    """Compute precise ETA timestamp (UTC ISO-8601) used by 'Guaranteed Visa on …'.

    - process_days=0  -> same day, 23:59 UTC
    - process_days>0  -> +N days at 23:59 UTC (gives a concrete deadline)
    - None            -> None (frontend hides the line)
    """
    if process_days is None:
        return None
    base = datetime.now(timezone.utc).replace(hour=23, minute=59, second=0, microsecond=0)
    eta = base + timedelta(days=process_days)
    return eta.isoformat().replace("+00:00", "Z")


@router.get("", response_model=ApiResponse[List[DestinationOut]])
async def list_destinations(
    db: AsyncSession = Depends(get_db),
    visa_type: Optional[str] = Query(None, description="按签种过滤: tourism | student"),
    lang: str = Query("zh-CN", description="返回国家名的语种: zh-CN | en | id | vi"),
):
    """返回国家列表。
    Spec: V2 范围 = 美国 enabled=true,其他 8 国 enabled=false(灰显,V3+ 开放)。
    """
    stmt = select(VisaDestination).order_by(VisaDestination.display_order)
    if visa_type:
        # visa_types 字段是 JSON 字符串,需要客户端或 DB 层过滤;这里只过滤 enabled
        pass
    rows = (await db.execute(stmt)).scalars().all()

    items = []
    for r in rows:
        # country_name_i18n 既可能是 JSON {"zh-CN":"...","en":"..."} (新格式)
        # 也可能是 legacy "美国 United States" 这种单字符串(老数据)
        try:
            name_map = json.loads(r.country_name_i18n)
            if not isinstance(name_map, dict):
                raise ValueError("not a dict")
        except Exception:
            # legacy 单字符串 — 启发式 split: 第一个空白之前是中文, 之后是英文
            s = (r.country_name_i18n or "").strip()
            name_map = {"zh-CN": s, "en": s or r.country_code}
            if " " in s:
                idx = s.find(" ")
                zh, en = s[:idx], s[idx + 1:].strip()
                if zh and en:
                    name_map = {"zh-CN": zh, "en": en}
        # W45 fix: 1) never return the raw country code (e.g. "AT"/"US") as a
        # human-readable country name on the destination card — the DB column
        # might be missing the requested locale (legacy seed_schengen_26 wrote
        # only English), and the legacy fallback above would otherwise hand back
        # the alpha-2 code. Use the hard-coded EN fallback for en-US, and mirror
        # the same string for any missing locale (acceptable for an MVP — the
        # fallback lives in code, not data, so we can replace it with proper
        # translations without a re-seed).
        # 2) when even the EN slot is missing, fall back to the EN table.
        en_default = name_map.get("en") or _COUNTRY_NAME_EN_FALLBACK.get(
            r.country_code, r.country_code
        )
        name_map.setdefault("en", en_default)
        # 3) ensure any requested locale gets *some* non-code string.
        name_map.setdefault(lang, en_default)
        if visa_type:
            try:
                types = json.loads(r.visa_types)
            except Exception:
                types = []
            if visa_type not in types:
                continue
        items.append(DestinationOut(
            id=r.id,
            country_code=r.country_code,
            country_name=name_map.get(lang) or name_map.get("en") or _COUNTRY_NAME_EN_FALLBACK.get(r.country_code, r.country_code),
            visa_types=json.loads(r.visa_types) if r.visa_types else [],
            image_url=r.image_url,
            enabled=r.enabled,
            visa_fee_usd=getattr(r, "visa_fee_usd", None),
            valid_days=getattr(r, "valid_days", None),
            process_days=getattr(r, "process_days", None),
            eta_iso=_compute_eta_iso(getattr(r, "process_days", None)),
        ))

    return ApiResponse(code="1000", message="OK", data=items)