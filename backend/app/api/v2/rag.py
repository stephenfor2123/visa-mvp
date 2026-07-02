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


# --------------------------------------------------------------------------- #
# Per-language config (header keywords, terminators, material keywords, strip chars)
# --------------------------------------------------------------------------- #
_LANG_CONFIG = {
    "zh-CN": {
        "section_header": r"(?:所需材料|基础材料)(?::|：)",
        "terminators": r"\n\n|签证费(?::|：)|审理时间(?::|：)|签证可在|使馆(?::|：)|联系方|官网(?::|：)|面签预约(?::|：)|电子签|常见拒|提高通过|面试常见问题|经济材料",
        "strip_chars": " ,。、;：",
        # Match-these-keywords ⇒ this row is a material
        "material_keywords": [
            "护照", "照片", "身份证", "户口", "证明", "申请表", "流水", "存款",
            "机票", "酒店", "行程", "保险", "邀请函", "营业执照", "确认页",
            "签证表", "保单", "税单", "税证明", "在职", "在读", "DS-160",
            "mm", "cm", "复印件", "原件",
        ],
        # Fee/processing/validity extraction regexes (line-oriented)
        "fee_patterns": [
            # Skip the section-title variant 签证费用与审理时间 which appears
            # as a header (no actual fee amount). Prefer lines with a digit.
            r"签证费(?::|：)?\s*[^。\n]{0,80}?\d+[^。\n]{0,40}",
            r"签证费用(?::|：)?\s*[^。\n]{0,80}?\d+[^。\n]{0,40}",
            r"费用(?::|：)?\s*[^。\n]{0,80}?\d+[^。\n]{0,40}",
            r"MRV\s*费(?::|：)?\s*[^\n。]{0,40}",
        ],
        "processing_patterns": [
            r"审理时间(?::|：)?\s*[^\n。]{0,60}",
            r"审批通常\s*\d+[\-–]\d*\s*个工作日",
            r"\d+\s*个工作日出?签",
        ],
        "validity_patterns": [
            r"有效期(?::|：)?\s*[^\n。]{0,60}",
            r"可停留[^\n。]{0,40}",
        ],
        # Retrieval fallback query template
        "retrieval_query_tpl": "{country_name} 签证 所需材料 材料清单",
    },
    "en": {
        "section_header": r"(?:Required\s+Materials?|Documents?\s+Required)[^\n]*?(?::|：)",
        "terminators": r"\n\n|Fee(?::|：)|Processing\s+Time|Validity|Stay|Embassy|Contact|Official\s+Website|Interview\s+Booking|eVisa|Common\s+Rejection|Tips\s+for\s+Approval|Interview\s+FAQ|Financial\s+Documents",
        "strip_chars": " ,.;:",
        "material_keywords": [
            "passport", "photo", "photograph", "identification", "id card",
            "household", "certificate", "application form", "bank statement",
            "deposit", "flight", "hotel", "itinerary", "insurance",
            "invitation", "business license", "confirmation",
            "DS-160", "mm", "cm", "copy", "original", "proof",
        ],
        "fee_patterns": [
            r"(?:Visa\s+Fee|Application\s+Fee|Fee)(?::|：)?[ \t]*(?:[$£€¥])?\s*(?:USD|GBP|EUR|AUD|CNY)?[ \t]*(?:[$£€¥])?\s*\d[\d,.]*(?:\s*(?:USD|GBP|EUR|AUD|CNY))?[^\n.]*",
            r"MRV\s*Fee(?::|：)?[ \t]*[^\n.]*",
            r"(?:USD|GBP|EUR|AUD|CNY)[ \t]*[$£€¥]?[ \t]*\d[\d,.]*",
        ],
        "processing_patterns": [
            r"(?:Processing\s+Time|Processing)[ \t]*(?::|：)[ \t]*[^\n]+",
            r"\d+\s*(?:to\s*\d+\s*)?business\s+days?",
            r"\d+\s*-\s*\d+\s*working\s+days?",
        ],
        "validity_patterns": [
            r"(?:Validity|Valid\s+for)[ \t]*(?::|：)[ \t]*[^\n]+",
            r"(?:Stay|Stay\s+Duration|Maximum\s+Stay)[ \t]*(?::|：)[ \t]*[^\n]+",
        ],
        "retrieval_query_tpl": "{country_name} visa required documents checklist",
    },
    "id": {
        # Indonesian: header appears as a label followed by a colon, e.g.
        #   "Dokumen yang Dibutuhkan untuk Visa Standard Visitor Inggris:"
        # We anchor on the colon so the regex matches regardless of what
        # sits between the header keyword and the colon.
        "section_header": r"(?:Dokumen\s+yang\s+Dibutuhkan|Persyaratan\s+Dokumen|Dokumen\s+diperlukan)[^\n]*?(?::|：)",
        "terminators": r"\n\n|Biaya(?::|：)|Waktu\s+Proses|Masa\s+Berlaku|Durasi\s+Tinggal|Kedutaan|Kontak|Situs\s+Resmi|Pemesanan\s+Wawancara|eVisa|Alasan\s+Penolakan\s+Umum|Tips\s+Persetujuan|FAQ\s+Wawancara|Dokumen\s+Keuangan",
        "strip_chars": " ,.;:",
        "material_keywords": [
            "paspor", "foto", "identitas", "ktp", "kartu keluarga", "sertifikat",
            "formulir aplikasi", "formulir pendaftaran", "rekening koran",
            "deposito", "penerbangan", "hotel", "itinierari", "asuransi",
            "surat undangan", "izin usaha", "konfirmasi",
            "DS-160", "mm", "cm", "salinan", "asli", "bukti",
        ],
        "fee_patterns": [
            r"(?:Biaya\s+Visa|Biaya\s+Aplikasi|Biaya)(?::|：)?[ \t]*(?:[$£€¥])?\s*(?:Rp\.?|IDR|USD|GBP|EUR|AUD|CNY)?[ \t]*(?:[$£€¥])?\s*\d[\d.,]*(?:\s*(?:Rp\.?|IDR|USD|GBP|EUR|AUD|CNY))?[^\n.]*",
            r"(?:Rp\.?|IDR|USD|GBP|EUR|AUD|CNY)[ \t]*[$£€¥]?[ \t]*\d[\d.,]*",
        ],
        "processing_patterns": [
            r"(?:Waktu\s+Proses|Pemrosesan)[ \t]*(?::|：)[ \t]*[^\n]+",
            r"\d+\s*(?:hingga\s*\d+\s*)?hari\s+kerja",
            r"\d+\s*-\s*\d+\s*hari\s+kerja",
        ],
        "validity_patterns": [
            r"(?:Masa\s+Berlaku|Berlaku\s+untuk|Durasi\s+Tinggal)[ \t]*(?::|：)[ \t]*[^\n]+",
        ],
        "retrieval_query_tpl": "{country_name} visa dokumen yang dibutuhkan",
    },
    "vi": {
        # Vietnamese header is followed by qualifier text before the colon,
        # e.g. "Giấy tờ cần thiết cho Vương quốc Anh:". Anchor on colon.
        "section_header": r"(?:Giấy\s+tờ\s+cần\s+thiết|Tài\s+liệu\s+cần\s+thiết|Hồ\s+sơ\s+cần)[^\n]*?(?::|：)",
        "terminators": r"\n\n|Lệ\s+phí(?::|：)|Thời\s+gian\s+xử\s+lý|Thời\s+hạn|Thời\s+gian\s+lưu\s+trú|Đại\s+sứ\s+quán|Liên\s+hệ|Trang\s+web\s+chính\s+thức|Đặt\s+lịch\s+phỏng\s+vấn|eVisa|Lý\s+do\s+từ\s+chối\s+phổ\s+biến|Mẹo\s+phê\s+duyệt|Câu\s+hỏi\s+thường\s+gặp\s+về\s+phỏng\s+vấn|Giấy\s+tờ\s+tài\s+chính",
        "strip_chars": " ,.;:",
        "material_keywords": [
            "hộ chiếu", "ảnh", "cmnd", "cccd", "sổ hộ khẩu", "giấy chứng nhận",
            "đơn xin", "đơn đăng ký", "sao kê ngân hàng",
            "tiền gửi", "chuyến bay", "khách sạn", "lịch trình", "bảo hiểm",
            "thư mời", "giấy phép kinh doanh", "xác nhận",
            "DS-160", "mm", "cm", "bản sao", "bản gốc", "bằng chứng",
        ],
        "fee_patterns": [
            r"(?:Lệ\s+phí\s+Visa|Lệ\s+phí\s+Đơn|Lệ\s+phí)(?::|：)?[ \t]*(?:[$£€¥])?\s*(?:VND|USD|GBP|EUR|AUD|CNY)?[ \t]*(?:[$£€¥])?\s*\d[\d.,]*(?:\s*(?:VND|USD|GBP|EUR|AUD|CNY))?[^\n.]*",
            r"(?:VND|USD|GBP|EUR|AUD|CNY)[ \t]*[$£€¥]?[ \t]*\d[\d.,]*",
        ],
        "processing_patterns": [
            r"(?:Thời\s+gian\s+xử\s+lý|Xử\s+lý)[ \t]*(?::|：)[ \t]*[^\n]+",
            r"\d+\s*(?:đến\s*\d+\s*)?ngày\s+làm\s+việc",
            r"\d+\s*-\s*\d+\s*ngày\s+làm\s+việc",
        ],
        "validity_patterns": [
            r"(?:Thời\s+hạn|Có\s+giá\s+trị\s+trong|Thời\s+gian\s+lưu\s+trú)[ \t]*(?::|：)[ \t]*[^\n]+",
        ],
        "retrieval_query_tpl": "{country_name} visa giấy tờ cần thiết",
    },
}


def _get_lang_config(lang: str) -> dict:
    """Return config dict for the requested language, falling back to en."""
    if lang in _LANG_CONFIG:
        return _LANG_CONFIG[lang]
    # Map common locale variants to the closest supported bucket
    short = lang.lower().split("-")[0]
    return _LANG_CONFIG.get(short, _LANG_CONFIG["en"])


def _parse_materials_from_text(text: str, lang: str = "zh-CN") -> List[MaterialItem]:
    """Extract material items from a chunk text containing a materials section.

    Pulls section header / terminator / keyword lists from the per-language
    config so all four supported languages (zh-CN, en, id, vi) parse with the
    same algorithm — only the language-specific regexes differ.
    """
    cfg = _get_lang_config(lang)
    items: List[MaterialItem] = []
    # The section_header pattern is anchored on its trailing colon, so the
    # captured group starts immediately after the header line ends.
    section_match = re.search(
        cfg["section_header"] + r"([\s\S]*?)(?:" + cfg["terminators"] + ")",
        text,
        flags=re.IGNORECASE,
    )
    if not section_match:
        # Fallback: take whatever comes after the header line
        m2 = re.search(cfg["section_header"] + r"([\s\S]+)", text, flags=re.IGNORECASE)
        if not m2:
            return items
        section = m2.group(1)[:600]
    else:
        section = section_match.group(1)

    raw_items = _split_respecting_parens(section)
    seen = set()
    for raw in raw_items:
        clean = raw.strip(cfg["strip_chars"])
        if not clean or len(clean) < 3 or len(clean) > 80:
            continue
        clean_lower = clean.lower()
        is_material = any(kw.lower() in clean_lower for kw in cfg["material_keywords"])
        if not is_material:
            continue
        if clean in seen:
            continue
        seen.add(clean)
        category = "base"
        for cat, kws in _MATERIAL_KEYWORDS:
            if any(kw.lower() in clean_lower for kw in kws):
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
    lang: Annotated[str, Query(min_length=2, max_length=8)] = "zh-CN",
) -> ApiResponse[ChecklistOut]:
    """Use RAG to extract required materials + meta (fee / processing time / validity).

    The ``lang`` query parameter selects which language of RAG chunks to read.
    If no chunks exist for the requested language the endpoint falls back to
    zh-CN (so the page never breaks when an English variant hasn't been
    seeded yet — a product-friendly default).
    """
    # Normalize lang → accepted bucket values
    requested_lang = (lang or "zh-CN").strip()
    is_english = requested_lang.startswith("en")

    # Look up the destination row for country name (pick by lang)
    from app.models.destination import VisaDestination
    import json as _json
    dest_row = (await db.execute(
        select(VisaDestination).where(VisaDestination.country_code == country_code.upper()).limit(1)
    )).scalar_one_or_none()
    if dest_row:
        try:
            i18n = _json.loads(dest_row.country_name_i18n)
            # Pick name in the requested language; fall back chain ensures we
            # always have something to display.
            primary_fallback = "zh-CN" if requested_lang == "zh-CN" else "en"
            country_name = (
                i18n.get(requested_lang)
                or i18n.get(primary_fallback)
                or i18n.get("en")
                or i18n.get("zh-CN")
                or country_code.upper()
            )
        except Exception:
            country_name = country_code.upper()
    else:
        country_name = country_code.upper()

    # Pull curated chunks first (they have the materials-list structure); fall
    # back to retrieval. Filter by language so we don't return Chinese text
    # when the user is on English mode.
    from app.models.rag import RagChunk, RagSource as RS

    async def _lookup_chunks(code: str, lang_bucket: str):
        stmt = (
            select(RagChunk, RS)
            .join(RS, RagChunk.source_id == RS.id)
            .where(RS.country_code == code)
            .where(RS.enabled.is_(True))
            .where(RS.language == lang_bucket)
            .order_by(RS.id, RagChunk.chunk_index)
        )
        return (await db.execute(stmt)).all()

    lookup_code = country_code.upper()
    # Try requested language first, then gracefully degrade to zh-CN so the
    # endpoint stays useful while we phase in English seed data country by
    # country.
    rows = await _lookup_chunks(lookup_code, requested_lang)
    effective_lang = requested_lang
    if not rows and requested_lang != "zh-CN":
        rows = await _lookup_chunks(lookup_code, "zh-CN")
        effective_lang = "zh-CN" if rows else requested_lang

    # W35: Schengen fallback — 26 member countries share one policy, seeded
    # only under "FR". Retry with the proxy code before giving up.
    if not rows and lookup_code in SCHENGEN_CODES and lookup_code != _SCHENGEN_RAG_PROXY_CODE:
        rows = await _lookup_chunks(_SCHENGEN_RAG_PROXY_CODE, requested_lang)
        if not rows and requested_lang != "zh-CN":
            rows = await _lookup_chunks(_SCHENGEN_RAG_PROXY_CODE, "zh-CN")
            effective_lang = "zh-CN" if rows else requested_lang

    full_text = ""
    materials: List[MaterialItem] = []
    source_name = None
    source_url = None
    if rows:
        # Concatenate all chunks for this country, then parse
        full_text = "\n\n".join(chunk.content for chunk, _ in rows)
        materials = _parse_materials_from_text(full_text, lang=effective_lang)
        source_name = rows[0][1].name
        source_url = rows[0][1].url
    else:
        # Fallback: live RAG retrieval with a checklist-flavored query
        retrieval_code = (
            _SCHENGEN_RAG_PROXY_CODE if lookup_code in SCHENGEN_CODES else lookup_code
        )
        retrieval_query = _get_lang_config(effective_lang)["retrieval_query_tpl"].format(
            country_name=country_name
        )
        retrieved = await retrieve(
            db,
            query=retrieval_query,
            country_code=retrieval_code,
            top_k=3,
        )
        full_text = "\n\n".join(r.text for r in retrieved)
        materials = _parse_materials_from_text(full_text, lang=effective_lang)
        source_name = retrieved[0].source_name if retrieved else None
        source_url = retrieved[0].source_url if retrieved else None

    # Extract fee / processing time / validity from full text using the
    # active language's regex set.
    cfg_meta = _get_lang_config(effective_lang)
    fee = _extract_meta(full_text, cfg_meta["fee_patterns"])
    processing_time = _extract_meta(full_text, cfg_meta["processing_patterns"])
    validity = _extract_meta(full_text, cfg_meta["validity_patterns"])

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
