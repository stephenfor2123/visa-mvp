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
from app.core.product_scope import (
    PRODUCT_DESTINATION_CODES,
    normalize_destination_code,
)
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


# W58: DB stores lang keys as short codes ('id' / 'vi' / 'en' / 'zh-CN'),
# but API callers (vue-i18n / LangSwitch / Destinations.vue) send BCP-47
# long codes ('id-ID' / 'vi-VN' / 'en-US' / 'zh-CN'). Normalise to short
# before lookup so an id-ID request finds the Indonesian translation
# instead of falling through to English. Falls through to the caller-
# supplied string if we don't recognise the prefix.
def _short_lang(tag: str) -> str:
    t = (tag or "").lower()
    if t.startswith("id"): return "id"
    if t.startswith("vi"): return "vi"
    if t.startswith("en"): return "en"
    if t.startswith("zh"): return "zh-CN"
    return tag


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
#
# W58: extended to 4-locale per code so the 26 Schengen countries (which only
# have a single English-name string in DB) have proper zh-CN / id / vi names on
# the destination card. EN is kept as the first key for backwards compatibility.
_COUNTRY_NAME_EN_FALLBACK = {
    "US": {"zh-CN": "美国", "en": "United States", "id": "Amerika Serikat", "vi": "Hoa Kỳ"},
    "AU": {"zh-CN": "澳大利亚", "en": "Australia", "id": "Australia", "vi": "Úc"},
    "GB": {"zh-CN": "英国", "en": "United Kingdom", "id": "Inggris", "vi": "Vương quốc Anh"},
    "DE": {"zh-CN": "德国(申根)", "en": "Germany", "id": "Jerman", "vi": "Đức"},
    "FR": {"zh-CN": "法国(申根)", "en": "France", "id": "Prancis", "vi": "Pháp"},
    "AT": {"zh-CN": "奥地利(申根)", "en": "Austria", "id": "Austria", "vi": "Áo"},
    "BE": {"zh-CN": "比利时(申根)", "en": "Belgium", "id": "Belgia", "vi": "Bỉ"},
    "HR": {"zh-CN": "克罗地亚(申根)", "en": "Croatia", "id": "Kroasia", "vi": "Croatia"},
    "CZ": {"zh-CN": "捷克(申根)", "en": "Czechia", "id": "Ceko", "vi": "Séc"},
    "DK": {"zh-CN": "丹麦(申根)", "en": "Denmark", "id": "Denmark", "vi": "Đan Mạch"},
    "EE": {"zh-CN": "爱沙尼亚(申根)", "en": "Estonia", "id": "Estonia", "vi": "Estonia"},
    "FI": {"zh-CN": "芬兰(申根)", "en": "Finland", "id": "Finlandia", "vi": "Phần Lan"},
    "GR": {"zh-CN": "希腊(申根)", "en": "Greece", "id": "Yunani", "vi": "Hy Lạp"},
    "HU": {"zh-CN": "匈牙利(申根)", "en": "Hungary", "id": "Hungaria", "vi": "Hungary"},
    "IS": {"zh-CN": "冰岛(申根)", "en": "Iceland", "id": "Islandia", "vi": "Iceland"},
    "IT": {"zh-CN": "意大利(申根)", "en": "Italy", "id": "Italia", "vi": "Ý"},
    "LV": {"zh-CN": "拉脱维亚(申根)", "en": "Latvia", "id": "Latvia", "vi": "Latvia"},
    "LI": {"zh-CN": "列支敦士登(申根)", "en": "Liechtenstein", "id": "Liechtenstein", "vi": "Liechtenstein"},
    "LT": {"zh-CN": "立陶宛(申根)", "en": "Lithuania", "id": "Lituania", "vi": "Litva"},
    "LU": {"zh-CN": "卢森堡(申根)", "en": "Luxembourg", "id": "Luksemburg", "vi": "Luxembourg"},
    "MT": {"zh-CN": "马耳他(申根)", "en": "Malta", "id": "Malta", "vi": "Malta"},
    "NL": {"zh-CN": "荷兰(申根)", "en": "Netherlands", "id": "Belanda", "vi": "Hà Lan"},
    "NO": {"zh-CN": "挪威(申根)", "en": "Norway", "id": "Norwegia", "vi": "Na Uy"},
    "PL": {"zh-CN": "波兰(申根)", "en": "Poland", "id": "Polandia", "vi": "Ba Lan"},
    "PT": {"zh-CN": "葡萄牙(申根)", "en": "Portugal", "id": "Portugal", "vi": "Bồ Đào Nha"},
    "SK": {"zh-CN": "斯洛伐克(申根)", "en": "Slovakia", "id": "Slovakia", "vi": "Slovakia"},
    "SI": {"zh-CN": "斯洛文尼亚(申根)", "en": "Slovenia", "id": "Slovenia", "vi": "Slovenia"},
    "ES": {"zh-CN": "西班牙(申根)", "en": "Spain", "id": "Spanyol", "vi": "Tây Ban Nha"},
    "SE": {"zh-CN": "瑞典(申根)", "en": "Sweden", "id": "Swedia", "vi": "Thụy Điển"},
    "SCHENGEN": {"zh-CN": "申根(任选 26 国)", "en": "Schengen (any of 26 members)",
                 "id": "Schengen (salah satu dari 26 negara)", "vi": "Schengen (một trong 26 quốc gia)"},
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

    产品口径(docs/PRODUCT_SCOPE.md): 仅美 / 英 / 澳 / 申根代表(DE·FR)。
    日本/加拿大/新加坡/新西兰/印尼/越南等不在办理范围,不出现在公开列表。
    """
    stmt = select(VisaDestination).order_by(VisaDestination.display_order)
    if visa_type:
        # visa_types 字段是 JSON 字符串,需要客户端或 DB 层过滤;这里只过滤 enabled
        pass
    rows = (await db.execute(stmt)).scalars().all()

    # Public product surface — drop non-product destinations entirely
    product_norm = {normalize_destination_code(c) for c in PRODUCT_DESTINATION_CODES}
    rows = [
        r for r in rows
        if normalize_destination_code(r.country_code) in product_norm
    ]

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
            has_cjk = any("\u4e00" <= c <= "\u9fff" for c in s)
            if s and not has_cjk and " " not in s:
                # English-only legacy seed (e.g. seed_schengen_26 wrote "Austria")
                name_map = {"en": s}
            elif " " in s:
                idx = s.find(" ")
                zh, en = s[:idx], s[idx + 1:].strip()
                if zh and en and has_cjk:
                    name_map = {"zh-CN": zh, "en": en}
                else:
                    name_map = {"en": s or r.country_code}
            else:
                name_map = {"zh-CN": s, "en": s or r.country_code}
        # W45 fix: 1) never return the raw country code (e.g. "AT"/"US") as a
        # human-readable country name on the destination card — the DB column
        # might be missing the requested locale (legacy seed_schengen_26 wrote
        # only English), and the legacy fallback above would otherwise hand back
        # the alpha-2 code. Use the hard-coded fallback table (W58: per-locale
        # strings) and mirror it for any missing locale (acceptable for an MVP —
        # the fallback lives in code, not data, so we can replace it with proper
        # translations without a re-seed).
        # 2) when even the EN slot is missing, fall back to the EN table.
        fb_entry = _COUNTRY_NAME_EN_FALLBACK.get(r.country_code)
        if isinstance(fb_entry, dict):
            fb_map = fb_entry
        elif isinstance(fb_entry, str):
            # Defensive: legacy callers / future edits passing a plain string still work.
            fb_map = {"en": fb_entry}
        else:
            fb_map = {"en": r.country_code}
        # EN layer: prefer what's in DB, then hard-coded EN.
        en_default = name_map.get("en") or fb_map.get("en") or r.country_code
        name_map.setdefault("en", en_default)
        short_lang = _short_lang(lang)
        # 3) ensure any requested locale gets *some* non-code string.
        # First, copy the per-locale strings from fb_map into name_map so the
        # caller's locale wins if present, otherwise we fill in from code.
        for lc in ("zh-CN", "id", "vi"):
            name_map.setdefault(lc, fb_map.get(lc) or en_default)
        name_map.setdefault(lang, en_default)
        name_map.setdefault(short_lang, en_default)
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
            # W58: try the short-code ('id' / 'vi') alias first so BCP-47 callers
            # ('id-ID' / 'vi-VN') get the right translation; fall back to the EN
            # slot and then the hard-coded fallback if nothing else.
            country_name=(
                name_map.get(short_lang)
                or name_map.get(lang)
                or name_map.get("en")
                or r.country_code
            ),
            visa_types=json.loads(r.visa_types) if r.visa_types else [],
            image_url=r.image_url,
            # Product destinations are always offered as available on this API
            enabled=True,
            visa_fee_usd=getattr(r, "visa_fee_usd", None),
            valid_days=getattr(r, "valid_days", None),
            process_days=getattr(r, "process_days", None),
            eta_iso=_compute_eta_iso(getattr(r, "process_days", None)),
        ))

    return ApiResponse(code="1000", message="OK", data=items)