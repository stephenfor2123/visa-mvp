"""/api/v2/rag — retrieval-augmented Q&A over official visa info.

Endpoints:
  GET    /api/v2/rag/sources          — list configured sources
  POST   /api/v2/rag/refresh          — admin: re-fetch + re-embed all (or one country)
  POST   /api/v2/rag/query            — user: ask a question, get top-k + answer
  GET    /api/v2/rag/checklist        — public: extract material checklist for a country (RAG)
"""
from __future__ import annotations

import re
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.middleware.admin_auth import verify_admin_token, AdminTokenData
from app.models.rag import RagSource
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.rag.refresh import refresh_all, refresh_source
from app.services.rag.retriever import generate_answer, generate_followups, retrieve

router = APIRouter(prefix="/rag", tags=["rag"])
_log = get_logger()


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #
class RagSourceOut(BaseModel):
    id: int
    name: str
    country_code: str
    url: Optional[str]
    content_type: str
    enabled: bool
    last_refresh_at: Optional[str]
    last_status: Optional[str]
    last_error: Optional[str]


class RagRefreshOut(BaseModel):
    refreshed: int
    errors: int
    items: List[dict]


class RagQueryRequest(BaseModel):
    query: str
    country_code: Optional[str] = None
    top_k: int = 3
    debug: bool = False  # W31: include per-chunk scoring breakdown


class RagChunkOut(BaseModel):
    chunk_id: int
    source_name: str
    source_url: Optional[str]
    score: float
    snippet: str


class RagQueryOut(BaseModel):
    query: str
    answer: str
    chunks: List[RagChunkOut]
    # W31: hybrid-search diagnostics + UX nudges
    followups: List[str] = []  # suggested follow-up questions
    debug: Optional[dict] = None  # per-chunk embedding/keyword score breakdown (only if debug=1)


class MaterialItem(BaseModel):
    """One material item extracted from RAG content."""
    name: str
    category: str  # base | financial | identity | travel | work
    required: bool = True
    note: Optional[str] = None


class ChecklistOut(BaseModel):
    country_code: str
    country_name: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    materials: List[MaterialItem]
    fee: Optional[str] = None
    processing_time: Optional[str] = None
    validity: Optional[str] = None
    notes: Optional[str] = None


# --------------------------------------------------------------------------- #
# Sources list                                                                #
# --------------------------------------------------------------------------- #
@router.get(
    "/sources",
    response_model=ApiResponse[List[RagSourceOut]],
    summary="List configured RAG sources",
)
async def list_sources(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[List[RagSourceOut]]:
    rows = (await db.execute(select(RagSource).order_by(RagSource.country_code, RagSource.id))).scalars().all()
    items = [
        RagSourceOut(
            id=r.id,
            name=r.name,
            country_code=r.country_code,
            url=r.url,
            content_type=r.content_type,
            enabled=r.enabled,
            last_refresh_at=r.last_refresh_at.isoformat() if r.last_refresh_at else None,
            last_status=r.last_status,
            last_error=r.last_error,
        )
        for r in rows
    ]
    return ApiResponse[List[RagSourceOut]](code="1000", message="OK", data=items)


# --------------------------------------------------------------------------- #
# Refresh (admin)                                                             #
# --------------------------------------------------------------------------- #
@router.post(
    "/refresh",
    response_model=ApiResponse[RagRefreshOut],
    summary="Refresh RAG sources (admin)",
)
async def refresh(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminTokenData, Depends(verify_admin_token)],
    country_code: Optional[str] = Query(None, description="Filter by country"),
) -> ApiResponse[RagRefreshOut]:
    items = await refresh_all(db, country_code=country_code)
    errors = sum(1 for x in items if x.get("status") == "error")
    refreshed = sum(1 for x in items if x.get("status") == "ok")
    return ApiResponse[RagRefreshOut](
        code="1000",
        message="OK",
        data=RagRefreshOut(refreshed=refreshed, errors=errors, items=items),
    )


# --------------------------------------------------------------------------- #
# Query (user)                                                                #
# --------------------------------------------------------------------------- #
@router.post(
    "/query",
    response_model=ApiResponse[RagQueryOut],
    summary="Ask a question; retrieve top-k chunks + generated answer",
)
async def query(
    body: RagQueryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[RagQueryOut]:
    # W31: Public — visa knowledge base, no personal data involved
    retrieved = await retrieve(
        db,
        query=body.query,
        country_code=body.country_code,
        top_k=body.top_k,
    )
    answer = generate_answer(body.query, retrieved)
    chunks = [
        RagChunkOut(
            chunk_id=r.chunk_id,
            source_name=r.source_name,
            source_url=r.source_url,
            score=round(r.score, 4),
            snippet=r.text[:300] + ("..." if len(r.text) > 300 else ""),
        )
        for r in retrieved
    ]
    followups = generate_followups(retrieved)
    debug = None
    if body.debug:
        debug = {
            "hybrid_weights": {"embedding": 0.45, "keyword": 0.55},
            "chunks": [
                {
                    "chunk_id": r.chunk_id,
                    "final_score": round(r.score, 4),
                    "embedding_score": round(r.embedding_score, 4),
                    "keyword_score": round(r.keyword_score, 4),
                    "matched_keywords": r.matched_keywords,
                }
                for r in retrieved
            ],
        }
    return ApiResponse[RagQueryOut](
        code="1000",
        message="OK",
        data=RagQueryOut(
            query=body.query,
            answer=answer,
            chunks=chunks,
            followups=followups,
            debug=debug,
        ),
    )


# --------------------------------------------------------------------------- #
# Checklist (public) — extract material list from RAG for a country            #
# --------------------------------------------------------------------------- #
_MATERIAL_KEYWORDS = [
    # (category, list of name keywords to match)
    # W38: "insurance" checked before "travel" — insurance item descriptions
    # often contain "...涵盖整个行程" (covers the whole itinerary), and "行程"
    # is also a travel keyword; if travel were checked first every insurance
    # item would get mis-bucketed into the travel group.
    ("identity", ["护照", "passport", "身份证", "户口", "照片", "photo", "白底", "证件"]),
    ("financial", ["银行流水", "bank statement", "存款", "存款证明", "财力", "纳税", "完税", "社保", "房产"]),
    ("work", ["在职", "在职证明", "employment", "营业执照", "公司", "在职证明", "在读", "学生证"]),
    ("insurance", ["保险", "insurance", "医疗保险"]),
    ("travel", ["机票", "行程单", "酒店", "预订", "itinerary", "酒店预订", "行程", "邀请函"]),
    ("form", ["申请表", "application form", "DS-160", "签证申请表", "evisa", "e-visa"]),
]


def _split_respecting_parens(section: str) -> List[str]:
    """按 顿号/分号/换行/英文逗号+空格 切分，但跳过括号 ()（）内部的分隔符。

    W38 fix: 旧版用 re.split 直接切，会把"护照原件 (有效期6个月以上, 至少1页
    空白)"这种括号里带逗号的描述从中间切断，产出"护照原件 (有效期6个月以上"
    和"至少1页空白)"两截头尾不接的碎片。这里改成手动扫描、记录括号深度，
    深度 > 0 时不切分。
    """
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    i = 0
    n = len(section)
    while i < n:
        ch = section[i]
        if ch in "（(":
            depth += 1
            buf.append(ch)
        elif ch in "）)":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif depth == 0 and ch in "、;；\n":
            parts.append("".join(buf))
            buf = []
        elif depth == 0 and ch == "," and i + 1 < n and section[i + 1] == " ":
            parts.append("".join(buf))
            buf = []
            i += 1  # 顺带跳过逗号后的空格
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _parse_materials_from_text(text: str) -> List[MaterialItem]:
    """Extract material items from a chunk text containing '所需材料' section.

    Strategy: stop at the next section header (签证费/审理时间/有效期/etc.) or
    end of paragraph, then split by 、 / ; / 。 / \\n, keeping bracketed details intact.
    """
    items: List[MaterialItem] = []
    # Find "所需材料" 段 — until the next Chinese section header or end
    m = re.search(r"(?:所需材料|基础材料)[:：]([\s\S]*?)(?:\n\n|签证费[:：]|审理时间[:：]|签证可在|使馆[:：]|联系方|官网[:：]|面签预约[:：]|电子签|常见拒|提高通过|面试常见问题|经济材料)", text)
    if not m:
        # Fallback: just take the whole text after 所需材料:
        m2 = re.search(r"所需材料[:：]([\s\S]+)", text)
        if not m2:
            return items
        section = m2.group(1)[:600]  # cap
    else:
        section = m.group(1)
    # W38 fix: 括号感知切分，不再用会切断括号内容的 re.split
    raw_items = _split_respecting_parens(section)
    seen = set()
    for raw in raw_items:
        # W38 fix: 不再把 （）() 放进 strip 的字符集——括号感知切分后条目
        # 本身括号是配对完整的，粗暴 strip 掉边缘括号反而会重新弄成不配对。
        clean = raw.strip(" ,。、;：")
        # Skip if too short/long, or if it looks like a sentence fragment
        if not clean or len(clean) < 3 or len(clean) > 50:
            continue
        # Skip fragments that are clearly not materials (sentences)
        # Materials usually end with: 复印件, 证明, 确认, 申请表, 保单, 流水, 单, 信
        # or contain size cm/mm indicators
        is_material = any(kw in clean for kw in [
            "护照", "照片", "身份证", "户口", "证明", "申请表", "流水", "存款",
            "机票", "酒店", "行程", "保险", "邀请函", "营业执照", "确认页",
            "签证表", "保单", "税单", "税证明", "在职", "在读", "DS-160",
            "mm", "cm", "复印件", "原件",
        ])
        if not is_material:
            continue
        if clean in seen:
            continue
        seen.add(clean)
        category = "base"
        for cat, kws in _MATERIAL_KEYWORDS:
            if any(kw in clean for kw in kws):
                category = cat
                break
        items.append(MaterialItem(name=clean, category=category, required=True))
    return items


# W35: the 26 Schengen member destinations share one visa policy, but the
# curated RAG content is only seeded under country_code="FR" (see
# scripts/seed_rag_sources.py). Without this fallback, picking any Schengen
# country other than France returns an empty checklist even though the
# content genuinely applies to it.
SCHENGEN_CODES = {
    "AT", "BE", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO",
    "PL", "PT", "SK", "SI", "ES", "SE", "CH",
}
_SCHENGEN_RAG_PROXY_CODE = "FR"


def _extract_meta(text: str, patterns: List[str]) -> Optional[str]:
    """Extract first matching line for a list of regex patterns."""
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0).strip()
    return None


@router.get(
    "/checklist",
    response_model=ApiResponse[ChecklistOut],
    summary="Material checklist for a country (RAG-extracted, public)",
)
async def checklist(
    db: Annotated[AsyncSession, Depends(get_db)],
    country_code: Annotated[str, Query(min_length=1, max_length=8)],
) -> ApiResponse[ChecklistOut]:
    """Use RAG to extract required materials + meta (fee / processing time / validity)."""
    # Look up the destination row for country name
    from app.models.destination import VisaDestination
    import json as _json
    dest_row = (await db.execute(
        select(VisaDestination).where(VisaDestination.country_code == country_code.upper()).limit(1)
    )).scalar_one_or_none()
    if dest_row:
        try:
            i18n = _json.loads(dest_row.country_name_i18n)
            country_name = i18n.get("zh-CN") or i18n.get("en") or country_code.upper()
        except Exception:
            country_name = country_code.upper()
    else:
        country_name = country_code.upper()

    # Pull curated chunks first (they have the "所需材料" structure); fall back to retrieval
    from app.models.rag import RagChunk, RagSource as RS

    async def _lookup_chunks(code: str):
        stmt = (
            select(RagChunk, RS)
            .join(RS, RagChunk.source_id == RS.id)
            .where(RS.country_code == code)
            .where(RS.enabled.is_(True))
            .order_by(RS.id, RagChunk.chunk_index)
        )
        return (await db.execute(stmt)).all()

    lookup_code = country_code.upper()
    rows = await _lookup_chunks(lookup_code)
    # W35: Schengen fallback — 26 member countries share one policy, seeded
    # only under "FR". Retry with the proxy code before giving up.
    if not rows and lookup_code in SCHENGEN_CODES and lookup_code != _SCHENGEN_RAG_PROXY_CODE:
        rows = await _lookup_chunks(_SCHENGEN_RAG_PROXY_CODE)

    if rows:
        # Concatenate all chunks for this country, then parse
        full_text = "\n\n".join(chunk.content for chunk, _ in rows)
        materials = _parse_materials_from_text(full_text)
        source_name = rows[0][1].name
        source_url = rows[0][1].url
    else:
        # Fallback: live RAG retrieval with a checklist-flavored query
        retrieval_code = (
            _SCHENGEN_RAG_PROXY_CODE if lookup_code in SCHENGEN_CODES else lookup_code
        )
        retrieved = await retrieve(
            db,
            query=f"{country_name} 签证 所需材料 材料清单",
            country_code=retrieval_code,
            top_k=3,
        )
        full_text = "\n\n".join(r.text for r in retrieved)
        materials = _parse_materials_from_text(full_text)
        source_name = retrieved[0].source_name if retrieved else None
        source_url = retrieved[0].source_url if retrieved else None

    # Extract fee / processing time / validity from full text
    fee = _extract_meta(full_text, [
        r"签证费[:：]?\s*[^\n。]{0,60}",
        r"费用[:：]?\s*[^\n。]{0,60}",
        r"MRV\s*费[:：]?\s*[^\n。]{0,40}",
    ])
    processing_time = _extract_meta(full_text, [
        r"审理时间[:：]?\s*[^\n。]{0,60}",
        r"审批通常\s*\d+[\-–]\d*\s*个工作日",
        r"\d+\s*个工作日出?签",
    ])
    validity = _extract_meta(full_text, [
        r"有效期[:：]?\s*[^\n。]{0,60}",
        r"可停留[^\n。]{0,40}",
    ])

    return ApiResponse[ChecklistOut](
        code="1000",
        message="OK",
        data=ChecklistOut(
            country_code=country_code.upper(),
            country_name=country_name,
            source_name=source_name,
            source_url=source_url,
            materials=materials,
            fee=fee,
            processing_time=processing_time,
            validity=validity,
            notes=None,
        ),
    )
