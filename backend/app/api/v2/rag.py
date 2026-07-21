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
from app.core.product_scope import normalize_destination_code
from app.core.security import get_current_user
from app.middleware.admin_auth import verify_admin_token, AdminTokenData
from app.models.rag import RagSource
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.rag.refresh import refresh_all, refresh_source
from app.services.rag.answer import answer_user_query
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
    # W47c: user-facing language. Empty/"en" → answers returned in English.
    # Anything else (zh-CN, id, vi) → query is translated to English for
    # retrieval and the answer is translated back into user_lang.
    user_lang: Optional[str] = None


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
    # W47c: pipeline observability — when debug=1 we expose the English
    # query / English answer alongside the user-facing render. Lets the UI
    # show "source query (en): …" for QA without polluting normal responses.
    user_lang: Optional[str] = None


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
    # W62+ — 让 C 端用户能感知到 "这条材料清单来自 RAG / 最后更新 / 有更新待审核"
    last_refresh_at: Optional[str] = None
    review_status: Optional[str] = None  # synced | pending_review | ...


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
    # W47c: English-authoritative pipeline (query-translate, retrieve-en,
    # answer-translate). user_lang drives the language; absent / "en" / "EN*"
    # → answer in English.
    composed = await answer_user_query(
        db,
        query=body.query,
        country_code=body.country_code,
        user_lang=body.user_lang,
        top_k=body.top_k,
        debug=body.debug,
    )
    chunks = [
        RagChunkOut(
            chunk_id=r.chunk_id,
            source_name=r.source_name,
            source_url=r.source_url,
            score=round(r.score, 4),
            snippet=r.text[:300] + ("..." if len(r.text) > 300 else ""),
        )
        for r in composed.chunks
    ]
    debug = None
    if body.debug:
        debug = {
            "hybrid_weights": {"embedding": 0.45, "keyword": 0.55},
            "user_lang": composed.user_lang,
            "en_query": composed.en_query,
            "en_answer": composed.en_answer,
            "chunks": [
                {
                    "chunk_id": r.chunk_id,
                    "final_score": round(r.score, 4),
                    "embedding_score": round(r.embedding_score, 4),
                    "keyword_score": round(r.keyword_score, 4),
                    "matched_keywords": r.matched_keywords,
                }
                for r in composed.chunks
            ],
        }
    return ApiResponse[RagQueryOut](
        code="1000",
        message="OK",
        data=RagQueryOut(
            query=composed.query,
            answer=composed.answer,
            chunks=chunks,
            followups=composed.followups,
            debug=debug,
            user_lang=composed.user_lang,
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
    """按 编号优先 → 顿号/分号/换行 切分，但跳过括号 ()（）内部的逗号/顿号。

    W38 fix: 旧版用 re.split 直接切，会把"护照原件 (有效期6个月以上, 至少1页
    空白)"这种括号里带逗号的描述从中间切断，产出"护照原件 (有效期6个月以上"
    和"至少1页空白)"两截头尾不接的碎片。这里改成手动扫描、记录括号深度，
    深度 > 0 时不切分。

    W47d fix: chunk 原文里多条材料经常共用同一段括号说明（例："1. 护照
    （有效期 6 个月以上；每名家庭成员须单独申请）"），括号内的 ;； 是
    并列子句分隔符，不切会把整段当一条材料。规则改成:
      - 深度=0 时: 切 \n / 编号 / ;；
      - 深度>0 时: 允许 ;； 切（视为并列子句边界），保护 、 与逗号
      - 切完后,如果是 "prefix（被切掉的内部）" 结构,自动把 prefix 复制
        给每个内部子段,保证每条材料都自包含。

    输出每个 item 形如 "1. 有效护照（有效期 6 个月以上，除非中美协议另有规定）"
    或 "1. 有效护照（每名需要签证的家庭成员须单独申请）"。
    """
    section = section.replace("\r\n", "\n").replace("\r", "\n")

    # 一次扫描：按规则切分并保留每段的"括号前缀"
    raw_segments: List[str] = []  # 每段可能形如 "1. 有效护照（"
    buf: List[str] = []
    depth = 0  # 0 = 在主层,1+ = 在括号内
    i = 0
    n = len(section)

    def _flush(depth_at_flush: int):
        """把当前 buf flush 到 raw_segments。

        如果 flush 时还在 depth>=1 (括号未闭合),把"前缀+括号头部"也算
        在该段里 —— 实际实现是:始终保留当前累积的所有字符,包括未闭合
        的开括号,后面会被外层按 ;； 再次切分。
        """
        raw_segments.append("".join(buf))
        buf.clear()

    while i < n:
        ch = section[i]

        # 编号标记: 深度=0 处,前面都是数字 + . / 、 / ) / ） 紧跟空白
        if (
            depth == 0
            and ch in ".,)、）"
            and buf
            and all(c.isdigit() for c in buf)
            and len(buf) <= 3
            and i + 1 < n
            and section[i + 1] in (" ", "\n", "\t")
        ):
            buf.append(ch)
            _flush(0)
            i += 1
            continue

        if ch == "\n" and depth == 0:
            _flush(0)
            i += 1
            continue

        if ch in "（(":
            depth += 1
            buf.append(ch)
        elif ch in "）)":
            depth = max(0, depth - 1)
            buf.append(ch)
            # 括号闭合如果回到 depth=0,且当前 buf 还没 flush,先 flush
            # 这样 "1. xxx（sub1；sub2）2. yyy" 会被切成 ["1. xxx（sub1；sub2）", "2. yyy"]
        elif depth >= 1 and ch in ";；":
            # 括号内的并列子句边界:切,depth 留在 1 (因为开括号还在 buf 里)
            # 用一个特殊 marker 区分"括号内并列切"和"主层切"
            buf.append("\x1f")  # 内部切分占位符,稍后处理
            i += 1
            continue
        elif depth == 0 and ch in ";；":
            # 主层的 ;； : 当作整段切
            _flush(0)
            i += 1
            continue
        elif depth == 0 and ch == "、":
            _flush(0)
            i += 1
            continue
        else:
            buf.append(ch)
        i += 1

    if buf:
        raw_segments.append("".join(buf))

    # 第二遍:把 "1. xxx（a\x1fb\x1fc）" 拆成 ["1. xxx（a）", "1. xxx（b）", "1. xxx（c）"]
    parts: List[str] = []
    for seg in raw_segments:
        seg = seg.strip()
        if not seg:
            continue
        if "\x1f" not in seg:
            parts.append(seg)
            continue
        # 找最外层括号位置
        m = re.match(r"^(.*?)([（(])(.*)$", seg, flags=re.DOTALL)
        if not m:
            # 没有外层括号结构,直接按 \x1f 切
            for sub in seg.split("\x1f"):
                sub = sub.strip()
                if sub:
                    parts.append(sub)
            continue
        prefix = m.group(1).rstrip()
        open_p = m.group(2)
        rest = m.group(3)
        # rest 以 )\x1f 之类的位置出现 —— 找到最后 ) 闭合
        if not rest.endswith(")") and not rest.endswith("）"):
            # 括号可能没闭合,直接切
            inner_pieces = [p.strip() for p in rest.split("\x1f") if p.strip()]
        else:
            close_p = rest[-1]
            inner = rest[:-1]
            inner_pieces = [p.strip() for p in inner.split("\x1f") if p.strip()]
        for ip in inner_pieces:
            # 去掉 ip 尾部可能附带的闭合括号 + 句末点 (顺序无关)
            # chunk 里通常末尾是 `)。` / `）` / `。` 之类
            ip = re.sub(r"[。.）)\s]+$", "", ip)
            parts.append(f"{prefix}{open_p}{ip}）")

    # 收尾:剥掉每段末尾的 "原 chunk 段尾标点" 但**不能剥掉编号或正常括号**
    # 规则:
    #  - 末尾是 `)。` / `）` 之类 (闭括号 + 句点) 时,只剥点保留闭括号
    #  - 末尾是 `。` (中文句号,前面没闭括号) 时,剥掉
    #  - **末尾是孤立的 `.`** (英文 dot,通常是 "1." 这种编号尾巴) **不剥**
    #    否则 en 段 "1." 会被剥成 "1",材料序号全乱。
    cleaned: List[str] = []
    for p in parts:
        # 1) "）。" / ")." 这种"闭括号+句末点" 的尾巴只剥点
        if re.search(r"[）)][。.]$", p):
            p = p[:-1]
        # 2) 中文句号 `。` (前面没有闭括号): 剥
        elif re.search(r"。[^a-zA-Z0-9]*$", p) and not re.search(r"[）)]$", p):
            p = re.sub(r"。[^a-zA-Z0-9]*$", "", p)
        # 3) 英文末尾的 . 但前面是数字 (e.g. "1." / "2." 编号尾巴) — 保留
        # 4) 英文末尾的 . 但前面是字母 (e.g. "...fee.") — 剥 (句末点)
        elif re.search(r"[a-zA-Z]\.$", p):
            p = p[:-1]
        cleaned.append(p)
    return cleaned

    return parts


# --------------------------------------------------------------------------- #
# Per-language config (header keywords, terminators, material keywords, strip chars)
# --------------------------------------------------------------------------- #
_LANG_CONFIG = {
    "zh-CN": {
        # W47d: chunk titles often include parenthetical source attributions
        # like "所需材料（依据 travel.state.gov 整理）：" — allow any non-newline
        # filler between the header keyword and the trailing colon so the
        # regex matches regardless of what editorial text sits in between.
        "section_header": r"(?:所需材料|基础材料)[^\n]*?(?::|：)",
        # W47d: terminators anchored on `\n` to avoid false hits inside the
        # section (e.g. 审理时间 mentioned inline cuts the section early).
        "terminators": r"(?:\n\n|\n)(?:签证费(?::|：)|审理时间(?::|：)|签证可在|使馆(?::|：)|联系方|官网(?::|：)|面签预约(?::|：)|电子签|常见拒|提高通过|面试常见问题|经济材料)",
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
            r"有效期(?::|：)?\s*[^\n。;；]{0,60}",
            r"可停留[^\n。;；]{0,40}",
        ],
        # Retrieval fallback query template
        "retrieval_query_tpl": "{country_name} 签证 所需材料 材料清单",
    },
    "en": {
        # W47d: cover all three phrasings used in curated FAQs:
        #   "Required Materials (...)", "Required Documents (...)",
        #   "Documents Required (...)". Also accept parenthetical filler
        #   between the header keyword and the trailing colon.
        "section_header": r"(?:Required\s+(?:Materials?|Documents?)|Documents?\s+Required)[^\n]*?(?::|：)",
        # W47d: terminators must anchor at a line/paragraph boundary — bare
        # `Stay`/`Validity` matched inline phrases like "period of stay" and
        # chopped the section at item 1. Require a leading `\n` (or `\n\n`)
        # so we only break on section headers, not inline word matches.
        "terminators": r"(?:\n\n|\n)(?:Fee(?::|：)|Processing\s+Time|Validity|Stay|Embassy|Contact|Official\s+Website|Interview\s+Booking|eVisa|Common\s+Rejection|Tips\s+for\s+Approval|Interview\s+FAQ|Financial\s+Documents)",
        "strip_chars": " ,.;:",
        "material_keywords": [
            "passport", "photo", "photograph", "identification", "id card",
            "household", "certificate", "application form", "application fee",
            "fee payment", "bank statement",
            "deposit", "flight", "hotel", "itinerary", "insurance",
            "invitation", "business license", "confirmation",
            "DS-160", "MRV", "mm", "cm", "copy", "original", "proof",
            "valid", "supporting documents", "support", "letter",
            "employment", "tax", "income", "assets", "financial",
        ],
        "fee_patterns": [
            # "Application (MRV) fee: $185 USD" — 中间可夹任意 () 注释。
            # _extract_meta 内部会 re.IGNORECASE,所以 [Ff]ee 这里写 [Ff]ee
            # 也能匹配 Fee/fee/FEE,但 Fee 单独写也能 match (忽略大小写)。
            r"(?:Application|Visa)\s*(?:\([^)]*\)\s*)?[Ff]ee(?::|：)?[ \t]*[\$£€¥]?\s*(?:USD|GBP|EUR|AUD|CNY)?[ \t]*[\$£€¥]?\s*\d[\d,.]*(?:\s*(?:USD|GBP|EUR|AUD|CNY))?[^\n.]*",
            r"MRV\s*[Ff]ee(?::|：)?[ \t]*[^\n.]*",
            r"Application\s+[Cc]harge(?::|：)?[ \t]*[\$£€¥]?\s*(?:USD|GBP|EUR|AUD)?[ \t]*[\$£€¥]?\s*\d[\d,.]*[^\n.]*",
            # 任意顺序的 currency+number: $185 USD / USD 185
            r"[\$£€¥]\s*\d[\d.,]*\s*(?:USD|GBP|EUR|AUD|CNY)",
            r"(?:USD|GBP|EUR|AUD|CNY)[ \t]*[\$£€¥]?[ \t]*\d[\d,.]*",
        ],
        "processing_patterns": [
            r"(?:Processing\s+Time|Processing|Standard\s+Decision\s+Time)[ \t]*(?::|：)[ \t]*[^\n]+",
            r"\d+\s*(?:to\s*\d+|\-\s*\d+)?\s*business\s+days?",
            r"\d+\s*-\s*\d+\s*(?:working|business)\s*days?",
            r"\d+\s*calendar\s+days?",
        ],
        "validity_patterns": [
            r"(?:Validity|Valid\s+for)(?::|：)[ \t]*[A-Z0-9][^\n]+",
            r"(?:Stay|Stay\s+Duration|Maximum\s+Stay)(?::|：)[ \t]*[A-Z0-9][^\n]+",
        ],
        "retrieval_query_tpl": "{country_name} visa required documents checklist",
    },
    "id": {
        # Indonesian: header appears as a label followed by a colon, e.g.
        #   "Dokumen yang Dibutuhkan untuk Visa Standard Visitor Inggris:"
        #   "Dokumen yang Diperlukan (menurut travel.state.gov):"
        # W47d: previous regex `Dokumen\s+diperlukan` missed the mandatory
        # `yang` between `Dokumen` and `Diperlukan` — chunks consistently
        # say "Dokumen yang Diperlukan", so we anchor the middle word and
        # accept either capitalisation.
        "section_header": r"(?:Dokumen\s+yang\s+(?:Dibutuhkan|Diperlukan)|Persyaratan\s+Dokumen|Dokumen\s+yang\s+diperlukan)[^\n]*?(?::|：)",
        # W47d: terminators anchored on `\n` to avoid false hits inside the
        # section (e.g. Waktu Proses mentioned inline cuts the section).
        "terminators": r"(?:\n\n|\n)(?:Biaya(?::|：)|Waktu\s+Proses|Masa\s+Berlaku|Durasi\s+Tinggal|Kedutaan|Kontak|Situs\s+Resmi|Pemesanan\s+Wawancara|eVisa|Alasan\s+Penolakan\s+Umum|Tips\s+Persetujuan|FAQ\s+Wawancara|Dokumen\s+Keuangan)",
        "strip_chars": " ,.;:",
        "material_keywords": [
            "paspor", "foto", "identitas", "ktp", "kartu keluarga", "sertifikat",
            "formulir aplikasi", "formulir pendaftaran", "rekening koran",
            "deposito", "penerbangan", "hotel", "itinierari", "asuransi",
            "surat undangan", "izin usaha", "konfirmasi",
            "DS-160", "mm", "cm", "salinan", "asli", "bukti",
        ],
        "fee_patterns": [
            # "Biaya aplikasi (MRV): $185 USD" — "aplikasi" 在 id chunk 里小写开头,
            # 而 "Biaya\s+Aplikasi" 大写不会命中,加 lowercase 兼容 + 多 token。
            # 中间可夹 (MRV) 之类的注释。
            r"(?:Biaya\s+(?:[Vv]isa|[Aa]plikasi|[Pp]ermohonan)|[Ll]angganan\s+[Vv]isa)\s*(?:\([^)]*\)\s*)?(?::|：)?[ \t]*[\$£€¥]?\s*(?:Rp\.?|IDR|USD|GBP|EUR|AUD|CNY)?[ \t]*[\$£€¥]?\s*\d[\d.,]*(?:\s*(?:Rp\.?|IDR|USD|GBP|EUR|AUD|CNY))?[^\n.]*",
            # 任意顺序的 currency+number: $185 USD / USD 185 / $ 185
            r"[\$£€¥]\s*\d[\d.,]*\s*(?:USD|GBP|EUR|AUD|CNY|IDR|Rp\.?)",
            r"(?:Rp\.?|IDR|USD|GBP|EUR|AUD|CNY)[ \t]*[\$£€¥]?[ \t]*\d[\d.,]*",
        ],
        "processing_patterns": [
            r"(?:Waktu\s+Proses|Pemrosesan|Waktu\s+pemrosesan)[ \t]*(?::|：)[ \t]*[^\n]+",
            r"\d+\s*(?:hingga\s*\d+\s*)?hari\s+kerja",
            r"\d+\s*-\s*\d+\s*hari\s+kerja",
            r"\d+\s*(?:hingga\s*\d+\s*)?minggu",
        ],
        "validity_patterns": [
            # 一定要冒号 + 紧跟具体内容才算命中,避免匹配到 chunk 标题里的
            # "Masa Berlaku, …"。开头接受数字或大写字母(B-1/B-2 等签证代号)。
            r"(?:Masa\s+[Bb]erlaku|[Bb]erlaku\s+untuk|Durasi\s+Tinggal)(?::|：)[ \t]*[A-Z0-9][^\n]+",
        ],
        "retrieval_query_tpl": "{country_name} visa dokumen yang dibutuhkan",
    },
    "vi": {
        # Vietnamese header is followed by qualifier text before the colon,
        # e.g. "Giấy tờ cần thiết cho Vương quốc Anh:". Anchor on colon.
        "section_header": r"(?:Giấy\s+tờ\s+cần\s+thiết|Tài\s+liệu\s+cần\s+thiết|Hồ\s+sơ\s+cần)[^\n]*?(?::|：)",
        # W47d: terminators anchored on `\n` to avoid false hits inside the
        # section (e.g. Thời hạn mentioned inline cuts the section).
        "terminators": r"(?:\n\n|\n)(?:Lệ\s+phí(?::|：)|Thời\s+gian\s+xử\s+lý|Thời\s+hạn|Thời\s+gian\s+lưu\s+trú|Đại\s+sứ\s+quán|Liên\s+hệ|Trang\s+web\s+chính\s+thức|Đặt\s+lịch\s+phỏng\s+vấn|eVisa|Lý\s+do\s+từ\s+chối\s+phổ\s+biến|Mẹo\s+phê\s+duyệt|Câu\s+hỏi\s+thường\s+gặp\s+về\s+phỏng\s+vấn|Giấy\s+tờ\s+tài\s+chính)",
        "strip_chars": " ,.;:",
        "material_keywords": [
            "hộ chiếu", "ảnh", "cmnd", "cccd", "sổ hộ khẩu", "giấy chứng nhận",
            "đơn xin", "đơn đăng ký", "sao kê ngân hàng",
            "tiền gửi", "chuyến bay", "khách sạn", "lịch trình", "bảo hiểm",
            "thư mời", "giấy phép kinh doanh", "xác nhận",
            "DS-160", "mm", "cm", "bản sao", "bản gốc", "bằng chứng",
        ],
        "fee_patterns": [
            # "Lệ phí visa (MRV): $185 USD" — case-insensitive 由 _extract_meta 处理
            # "Lệ phí đơn" 还要兼容 "Lệ phí visa" / "Lệ phí đăng ký"
            r"(?:Lệ\s+phí\s+(?:visa|đơn|đăng\s+ký)|Phí\s+(?:visa|xét\s+duyệt))[ \t]*(?:\([^)]*\)\s*)?(?::|：)?[ \t]*[\$£€¥]?\s*(?:VND|USD|GBP|EUR|AUD|CNY)?[ \t]*[\$£€¥]?\s*\d[\d.,]*(?:\s*(?:VND|USD|GBP|EUR|AUD|CNY))?[^\n.]*",
            # 任意顺序的 currency+number: $185 USD / USD 185
            r"[\$£€¥]\s*\d[\d.,]*\s*(?:USD|GBP|EUR|AUD|CNY|VND)",
            r"(?:VND|USD|GBP|EUR|AUD|CNY)[ \t]*[\$£€¥]?[ \t]*\d[\d.,]*",
        ],
        "processing_patterns": [
            r"(?:Thời\s+gian\s+xử\s+lý|Xử\s+lý|Thời\s+gian\s+xét\s+duyệt)[ \t]*(?::|：)[ \t]*[^\n]+",
            r"\d+\s*(?:đến\s*\d+\s*)?ngày\s+làm\s+việc",
            r"\d+\s*-\s*\d+\s*ngày\s+làm\s+việc",
            r"\d+\s*(?:đến\s*\d+\s*)?tuần",
        ],
        "validity_patterns": [
            # 一定要冒号 + 紧跟具体内容(数字/单位/句子)才算命中,
            # 避免匹配到 chunk 标题里的 "Thời hạn …"
            r"(?:Thời\s+hạn|Có\s+giá\s+trị\s+trong|Thời\s+gian\s+lưu\s+trú)(?::|：)[ \t]*\d[^\n]+",
            r"(?:Thời\s+hạn|Có\s+giá\s+trị\s+trong|Thời\s+gian\s+lưu\s+trú)(?::|：)[ \t]*[A-ZÀ-Ỹ][^\n]+",
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
    # W47d fix: seed chunks occasionally carry markdown emphasis markers
    # (`**bold**`, `*em*`, `__underline__`) that should not leak into the UI.
    # Strip them globally before any regex matching.
    text = re.sub(r"\*+([^*]+?)\*+", r"\1", text)
    text = re.sub(r"_+(.+?)_+", r"\1", text)
    # The section_header pattern is anchored on its trailing colon, so the
    # captured group starts immediately after the header line ends.
    section_match = re.search(
        cfg["section_header"] + r"([\s\S]*?)(?:" + cfg["terminators"] + ")",
        text,
        flags=re.IGNORECASE,
    )
    if not section_match:
        # Fallback: take whatever comes after the header line up to the next
        # likely section header. We anchor on:
        #   1. A blank line followed by another section-like header
        #      (e.g. "Visitor Visa ... — Fees, Validity, and Stay:")
        #   2. The end of the text
        # 这样 en chunk_0 (没有 inline terminator) 能拿到所有 1-4 编号条目
        # 而不会撞到 chunk_1 的内容。
        m2 = re.search(cfg["section_header"] + r"([\s\S]+)", text, flags=re.IGNORECASE)
        if not m2:
            return items
        rest = m2.group(1)
        # next_header 锚:撞到下一个 "Title — Subtitle:" 形式的 section header 就停。
        # scan_offset 必须是 rest 长度的最小(80, len//3),以保证 chunk 拼接后能扫到。
        # W47d+ : 短 section (< 240 字符) 时 scan_offset=80 还是会过界,
        # 用 min(80, len//3) 兜底。
        scan_offset = min(80, max(0, len(rest) // 3))
        next_header = re.search(
            r"\n\n[A-Z][A-Za-z0-9 ()-—:/,&]{3,120}?[:：](?:\s*\n|$)",
            rest[scan_offset:],
        )
        if next_header:
            section = rest[: scan_offset + next_header.start()]
        else:
            section = rest
    else:
        section = section_match.group(1)

    raw_items = _split_respecting_parens(section)
    # W47d+ : 编号段 ("1." / "2.") 被 split 单独 flush 出去后,材料本体失去
    # 前缀 (变成 "Passport valid..." 开头),很难再判断是不是材料。
    # 这里合并:把孤立的编号段与其后第一段非编号段拼成一条。
    merged: List[str] = []
    num_re = re.compile(r"^\d+\s*[\.、)）]?$")
    pending_num: str = ""
    for seg in raw_items:
        s = seg.strip()
        if not s:
            continue
        if num_re.match(s):
            pending_num = s
            continue
        if pending_num:
            merged.append(f"{pending_num} {s}")
            pending_num = ""
        else:
            merged.append(s)
    if pending_num:
        merged.append(pending_num)

    seen = set()
    for raw in merged:
        clean = raw.strip(cfg["strip_chars"])
        if not clean or len(clean) < 3:
            continue
        # W47d+ : 80 字符上限对英文/印尼文/越南文太短,改成 400。
        if len(clean) > 400:
            continue
        clean_lower = clean.lower()
        starts_with_number = bool(re.match(r"^\d+\s*[\.、)）]", clean))
        # 收材料的两个条件,任一满足即收:
        #   A. 编号开头 (1. xxx / 1、xxx) — 长短不限,但不超过 400 字符
        #   B. 命中 material_keywords **且** 短 (≤80 字符)
        #      长段 (e.g. "A visitor visa is..." 介绍、整段说明) 不会因为
        #      偶然命中 "letter" / "support" 等 keyword 误收。
        hits_keyword = any(
            kw.lower() in clean_lower for kw in cfg["material_keywords"]
        )
        is_material = starts_with_number or (hits_keyword and len(clean) <= 80)
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
    # W47d: strip markdown emphasis so the captured meta text doesn't carry
    # stray `**` markers into the UI.
    text = re.sub(r"\*+([^*]+?)\*+", r"\1", text)
    text = re.sub(r"_+(.+?)_+", r"\1", text)
    for p in patterns:
        # W47d+ : iterate to find the first match that isn't a section title.
        # When the seeded chunk is structured as "Chunk 1 标题: 签证费用、有效期...",
        # the regex above can grab the title line ("有效期与申请方式(依据 GOV.UK):")
        # instead of an actual content line. Section titles tend to end with a
        # colon and contain "依据" / "per" markers, so we skip matches that
        # exhibit those signals and keep scanning for real content.
        for m in re.finditer(p, text):
            s = m.group(0).strip()
            # 剥掉末尾孤立的闭括号 (chunk 句式 `3. 签证申请费缴费收据（MRV 费 185 美元，面谈前缴纳）`
            # validity pattern `有效期(?::|：)?\s*[^\n。]{0,60}` 会贪心吃到 `）` 收尾)
            # 但不能剥掉句子中间的正常闭括号,所以只在末尾剥
            s = re.sub(r"[）)]\s*$", "", s)
            # 末尾的孤立 `。` / `.` 也剥掉
            s = re.sub(r"[。.\s]+$", "", s)
            # Skip section-title matches — they end with "依据 … :", "per … :",
            # or contain the marker fragment by themselves. Real content lines
            # usually have a numeric / verb payload ("6 个月", "5-15 个工作日").
            if s.endswith((":", "：")):
                continue
            if re.search(r"(?:依据|整理|per\s+[A-Za-z])", s) and len(s) < 25:
                continue
            if len(s) < 2:
                continue
            return s
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
    is_english_lang = requested_lang.startswith("en")
    raw_code = country_code.strip().upper()
    lookup_code = normalize_destination_code(raw_code)

    # Look up the destination row for country name (pick by lang)
    from app.models.destination import VisaDestination
    import json as _json
    # Production may still contain the historical UK code while RAG content
    # is canonicalised under GB. Accept either row for the display name.
    destination_codes = {raw_code, lookup_code}
    if lookup_code == "GB":
        destination_codes.add("UK")
    dest_row = (await db.execute(
        select(VisaDestination)
        .where(VisaDestination.country_code.in_(destination_codes))
        .limit(1)
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
                or lookup_code
            )
        except Exception:
            country_name = lookup_code
    else:
        country_name = lookup_code

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

    # W47d+ fallback chain: requested_lang → en → en-on-the-fly translate.
    # 之所以不直接 fallback 到 zh-CN:产品要求各语言版本只展示该语言或英文
    # (或英文翻译成该语言),不允许直接给用户看中文界面。
    rows = await _lookup_chunks(lookup_code, requested_lang)
    effective_lang = requested_lang
    if not rows and requested_lang != "en":
        rows = await _lookup_chunks(lookup_code, "en")
        if rows:
            effective_lang = "en"

    # W35: Schengen fallback — 26 member countries share one policy, seeded
    # only under "FR". Retry with the proxy code before giving up.
    if not rows and lookup_code in SCHENGEN_CODES and lookup_code != _SCHENGEN_RAG_PROXY_CODE:
        rows = await _lookup_chunks(_SCHENGEN_RAG_PROXY_CODE, requested_lang)
        effective_lang = requested_lang
        if not rows and requested_lang != "en":
            rows = await _lookup_chunks(_SCHENGEN_RAG_PROXY_CODE, "en")
            if rows:
                effective_lang = "en"

    full_text = ""
    materials: List[MaterialItem] = []
    source_name = None
    source_url = None
    if rows:
        # Concatenate all chunks for this country, then parse.
        # Materials extraction only needs chunk 0 (the "Required Documents"
        # section) — running it on the full join risks the parser's terminator
        # regex bleeding into chunk 1/2 (e.g. the chunk-2 "常见拒签原因:" line
        # would prematurely truncate the materials section). So we pass
        # chunk 0's content into the materials parser, while full_text
        # (used for fee/processing/validity meta extraction) stays joined.
        full_text = "\n\n".join(chunk.content for chunk, _ in rows)
        chunk0_text = next((c.content for c, _ in rows if c.chunk_index == 0), full_text)
        # Parse with the **active** language's parser (preserves quality of
        # the existing per-language section_header / terminator regexes).
        materials = _parse_materials_from_text(chunk0_text, lang=effective_lang)
        source_name = rows[0][1].name
        # source_url resolution priority:
        #   1. chunk-level source_url (W47c, filled by seed scripts per chunk)
        #   2. RagSource.url (country-level legacy link)
        #   3. None
        chunk_obj = next((c for c, _ in rows if c.chunk_index == 0), None)
        source_url = (
            (chunk_obj.source_url if chunk_obj and chunk_obj.source_url else None)
            or rows[0][1].url
            or None
        )
        # W47d+ : 如果 effective_lang="en" 但用户要的是另一种语言,把材料
        # 名称 (materials[].name) 翻译成目标语言。fee / processing_time /
        # validity 也一并翻译。
        if effective_lang == "en" and not is_english_lang and materials:
            from app.services.rag.translate import to_display_many
            names_to_translate = [m.name for m in materials]
            translated_names = await to_display_many(
                db, names_to_translate, requested_lang, kind="snippet"
            )
            materials = [
                MaterialItem(name=tn, category=m.category, required=m.required, note=m.note)
                for tn, m in zip(translated_names, materials)
            ]
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

    # W47d+ : 如果 effective_lang="en" 但用户要的是另一种语言,把
    # fee/processing_time/validity 也翻译成目标语言,跟 materials.name 保持一致
    if effective_lang == "en" and not is_english_lang:
        from app.services.rag.translate import to_display_many
        to_translate = []
        for v in (fee, processing_time, validity):
            if v:
                to_translate.append(v)
        if to_translate:
            translated = await to_display_many(db, to_translate, requested_lang, kind="snippet")
            idx = 0
            new_fee = fee
            new_proc = processing_time
            new_val = validity
            if fee:
                new_fee = translated[idx]; idx += 1
            if processing_time:
                new_proc = translated[idx]; idx += 1
            if validity:
                new_val = translated[idx]; idx += 1
            fee, processing_time, validity = new_fee, new_proc, new_val

    return ApiResponse[ChecklistOut](
        code="1000",
        message="OK",
        data=ChecklistOut(
            country_code=lookup_code,
            country_name=country_name,
            source_name=source_name,
            source_url=source_url,
            materials=materials,
            fee=fee,
            processing_time=processing_time,
            validity=validity,
            notes=None,
            last_refresh_at=(
                rows[0][1].last_refresh_at.isoformat() if rows and rows[0][1].last_refresh_at else None
            ),
            review_status=(
                rows[0][1].review_status if rows and rows[0][1].review_status else None
            ),
        ),
    )
