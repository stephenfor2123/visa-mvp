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
    ("identity", ["护照", "passport", "身份证", "户口", "照片", "photo", "白底", "证件"]),
    ("financial", ["银行流水", "bank statement", "存款", "存款证明", "财力", "纳税", "完税", "社保", "房产"]),
    ("work", ["在职", "在职证明", "employment", "营业执照", "公司", "在职证明", "在读", "学生证"]),
    ("travel", ["机票", "行程单", "酒店", "预订", "itinerary", "酒店预订", "行程", "邀请函"]),
    ("insurance", ["保险", "insurance", "医疗保险"]),
    ("form", ["申请表", "application form", "DS-160", "签证申请表", "evisa", "e-visa"]),
]


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
    # Split by 顿号 / 中英文分号 / 换行 / 英文逗号+空格, keep 括号完整
    raw_items = re.split(r"[、;；\n]|, (?=\S)", section)
    seen = set()
    for raw in raw_items:
        clean = raw.strip(" ,。、;：（）()")
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
    stmt = (
        select(RagChunk, RS)
        .join(RS, RagChunk.source_id == RS.id)
        .where(RS.country_code == country_code.upper())
        .where(RS.enabled.is_(True))
        .order_by(RS.id, RagChunk.chunk_index)
    )
    rows = (await db.execute(stmt)).all()
    if rows:
        # Concatenate all chunks for this country, then parse
        full_text = "\n\n".join(chunk.content for chunk, _ in rows)
        materials = _parse_materials_from_text(full_text)
        source_name = rows[0][1].name
        source_url = rows[0][1].url
    else:
        # Fallback: live RAG retrieval with a checklist-flavored query
        retrieved = await retrieve(
            db,
            query=f"{country_name} 签证 所需材料 材料清单",
            country_code=country_code.upper(),
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
