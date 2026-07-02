"""VisaDiagnoser — AI 拒签风险诊断 (V2 §4.3.5).

Engine:
  1. Completeness check — required docs for country/visa_type present?
  2. Field-level checks — passport validity, ID consistency, etc.
  3. RAG context — pull the country's official visa policy via app.services.rag
  4. Issue aggregation → overall risk score + categorized issues

Why rule-engine + RAG (not raw LLM)?
  - Deterministic baseline (testable, no hallucination on hard rules)
  - LLM fallback optional later (when external API configured)
  - RAG supplies per-country policy context so rules stay current
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.models.material import MATERIAL_TYPES

_log = get_logger()


# ---------------------------------------------------------------- #
# Country-specific checklists                                       #
# ---------------------------------------------------------------- #
# Per V2 §4.3.5 — minimum required materials per (country, visa_type).
# Source: requirements doc + Wikipedia + embassy pages (kept high-level).
# Each rule has a human-readable key, the material types expected,
# and a short failure reason template.
_REQUIRED: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "US": {
        # US tourist/business B1/B2
        "default": [
            {"key": "us.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "us.ds160",      "types": ["form"],       "reason": "需要 DS-160 确认页"},
            {"key": "us.photo",      "types": ["photo"],      "reason": "需要 51×51mm 白底照片"},
            {"key": "us.financial",  "types": ["other", "bank"], "reason": "建议提供银行流水 / 资产证明"},
            {"key": "us.itinerary",  "types": ["other", "flight", "hotel"], "reason": "建议提供行程单 / 邀请函"},
        ],
        "student": [
            {"key": "us.passport",   "types": ["passport"],   "reason": "需要护照"},
            {"key": "us.ds160",      "types": ["form"],       "reason": "需要 DS-160 确认页"},
            {"key": "us.i20",        "types": ["form"],       "reason": "需要 I-20 表 (学校签发)"},
            {"key": "us.sevis",      "types": ["other"],      "reason": "需要 SEVIS 缴费凭证"},
            {"key": "us.photo",      "types": ["photo"],      "reason": "需要 51×51mm 白底照片"},
            {"key": "us.financial",  "types": ["other", "bank"], "reason": "需要财力证明"},
        ],
    },
    "VN": {
        "default": [
            {"key": "vn.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "vn.photo",      "types": ["photo"],      "reason": "需要 2 寸白底照片"},
            {"key": "vn.form",       "types": ["form"],       "reason": "需要签证申请表 (NA1)"},
        ],
    },
    "ID": {
        "default": [
            {"key": "id.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "id.photo",      "types": ["photo"],      "reason": "需要红底或白底 2 寸照片"},
        ],
    },
    "TH": {
        "default": [
            {"key": "th.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "th.photo",      "types": ["photo"],      "reason": "需要 2 寸白底照片"},
            {"key": "th.financial",  "types": ["other", "bank"], "reason": "建议提供财力证明"},
        ],
    },
    "JP": {
        "default": [
            {"key": "jp.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "jp.photo",      "types": ["photo"],      "reason": "需要 4.5×4.5cm 白底照片"},
            {"key": "jp.form",       "types": ["form"],       "reason": "需要签证申请表"},
            {"key": "jp.itinerary",  "types": ["other", "flight", "hotel"], "reason": "需要行程单"},
            {"key": "jp.financial",  "types": ["other", "bank"], "reason": "需要银行流水"},
        ],
    },
    "KR": {
        "default": [
            {"key": "kr.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "kr.photo",      "types": ["photo"],      "reason": "需要白底 3.5×4.5cm 照片"},
            {"key": "kr.form",       "types": ["form"],       "reason": "需要签证申请表"},
        ],
    },
    "SG": {
        "default": [
            {"key": "sg.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "sg.photo",      "types": ["photo"],      "reason": "需要白底照片"},
            {"key": "sg.form",       "types": ["form"],       "reason": "需要申请表 (V14A / V39A)"},
        ],
    },
    "GB": {
        "default": [
            {"key": "gb.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照"},
            {"key": "gb.photo",      "types": ["photo"],      "reason": "需要 35×45mm 白底照片"},
            {"key": "gb.form",       "types": ["form"],       "reason": "需要在线申请表"},
            {"key": "gb.financial",  "types": ["other", "bank"], "reason": "需要财力证明"},
        ],
    },
}


# Severity weight per issue kind
_SEVERITY_WEIGHT = {
    "info": 0.0,
    "warning": 0.15,
    "error": 0.35,
    "critical": 0.6,
}


# ---------------------------------------------------------------- #
# Result types                                                      #
# ---------------------------------------------------------------- #
@dataclass
class DiagnoseIssue:
    code: str
    severity: str
    title: str
    detail: str
    fix_suggestion: Optional[str] = None
    related_material_id: Optional[int] = None
    # W39: raw values behind the zh-CN title/detail strings above, so a
    # frontend can re-render the message in the user's own locale via its
    # own i18n keyed by `code` instead of showing this server's zh-CN text.
    params: Optional[dict] = None


@dataclass
class DiagnoseOutput:
    overall_risk: str
    risk_score: float
    summary: str
    issues: List[DiagnoseIssue]
    positives: List[str]
    policy_refs: List[str]
    rule_count: int


# ---------------------------------------------------------------- #
# Diagnoser                                                         #
# ---------------------------------------------------------------- #
class VisaDiagnoser:
    """Diagnose refusal risk for a visa application."""

    # passport must have ≥ 6 months validity beyond travel date (or today)
    PASSPORT_MIN_VALIDITY_MONTHS = 6

    def __init__(self, rag_retriever=None):
        """rag_retriever is optional — pass app.services.rag.retriever.Retriever
        if you want policy context. Lazy import to avoid hard dep.
        """
        self._rag = rag_retriever

    def diagnose(
        self,
        *,
        materials: List[Dict[str, Any]],
        country_code: str,
        visa_type: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
    ) -> DiagnoseOutput:
        """Run the full diagnostic.

        :param materials: list of material dicts (must include id, material_type,
                          ocr_result, original_filename).
        :param country_code: ISO-2 destination country.
        :param visa_type: visa subclass (e.g. "student", "B1", "tourist"). None → default.
        :param fields: optional form fields (travel_date, purpose, etc.).
        """
        issues: List[DiagnoseIssue] = []
        positives: List[str] = []
        policy_refs: List[str] = []
        rule_count = 0

        country_code = (country_code or "").upper()
        fields = fields or {}

        # 1. Completeness — required docs present?
        required = self._required_for(country_code, visa_type)
        rule_count += len(required)
        present_types = {m.get("material_type") for m in materials}
        for req in required:
            if not any(t in present_types for t in req["types"]):
                issues.append(DiagnoseIssue(
                    code=req["key"],
                    severity="warning",
                    title=f"缺少{_country_name(country_code)}{_visa_label(visa_type)}申请必备材料",
                    detail=req["reason"],
                    fix_suggestion=f"请补充: {', '.join(_type_label(t) for t in req['types'])}",
                ))

        # 2. Field-level checks (one per material)
        for m in materials:
            mid = m.get("id")
            ocr = m.get("ocr_result") or {}
            # W39 fix: the only code path that actually persists Material.ocr_result
            # (POST /materials/{id}/ocr, see materials.py) writes a FLAT dict
            # (e.g. {"expiry": "...", "passport_no": "..."}) to match what
            # extractApplicantDraft() on the frontend expects. This used to read
            # ocr["fields"] (a nested shape no producer ever actually writes),
            # so ocr_fields was always {} and every passport was flagged as
            # missing its expiry even when OCR found one.
            ocr_fields = ocr if isinstance(ocr, dict) else {}
            mtype = m.get("material_type", "other")

            rule_count += 1

            # passport expiry check
            if mtype == "passport":
                expiry = (
                    ocr_fields.get("expiry")
                    or ocr_fields.get("date_of_expiry")
                    or ocr_fields.get("passport_expiry")
                )
                if not expiry:
                    # W45: ocr_fields.is_passport_doc == False 说明 OCR 压根没从图里
                    # 认出任何护照特征（不是"读到护照但缺有效期"），用更准确的提示，
                    # 不然用户看着明明是护照的图片却报"有效期缺失"会很困惑。
                    if ocr_fields.get("is_passport_doc") is False:
                        issues.append(DiagnoseIssue(
                            code="passport.not_detected",
                            severity="error",
                            title="未识别到护照信息",
                            detail="OCR 没有从这张图片里识别出任何护照特征（页眉、MRZ 码等），签证官会要求补交或直接拒签。",
                            fix_suggestion="请确认上传的是清晰、完整的护照资料页,不是户口本、照片或其他证件。",
                            related_material_id=mid,
                        ))
                    else:
                        issues.append(DiagnoseIssue(
                            code="passport.expiry_missing",
                            severity="error",
                            title="护照有效期字段缺失",
                            detail="OCR 未识别到护照有效期,签证官会要求补交或直接拒签。",
                            fix_suggestion="请上传清晰的护照首页扫描件,或手动填写有效期字段。",
                            related_material_id=mid,
                        ))
                else:
                    months_left = self._months_until(expiry)
                    if months_left is not None and months_left < self.PASSPORT_MIN_VALIDITY_MONTHS:
                        issues.append(DiagnoseIssue(
                            code="passport.expiry_short",
                            severity="critical",
                            title=f"护照有效期不足 {self.PASSPORT_MIN_VALIDITY_MONTHS} 个月",
                            detail=f"有效期 {expiry},剩余约 {months_left} 个月,大多数国家要求 ≥6 个月。",
                            fix_suggestion="出发前必须续期护照,否则会被直接拒签。",
                            related_material_id=mid,
                            params={"min_months": self.PASSPORT_MIN_VALIDITY_MONTHS, "expiry": expiry, "months_left": months_left},
                        ))
                    elif months_left is not None:
                        positives.append(f"护照有效期充足 ({expiry}, 约 {months_left} 个月)")

                # passport_no sanity
                pno = (
                    ocr_fields.get("passport_no")
                    or ocr_fields.get("passport_number")
                )
                if pno and not self._looks_like_passport_no(pno):
                    issues.append(DiagnoseIssue(
                        code="passport.no_suspicious",
                        severity="warning",
                        title="护照号格式异常",
                        detail=f"识别到的护照号 {pno!r} 不符合常见格式 (1 字母 + 7-8 位数字)。",
                        fix_suggestion="请确认上传的是护照资料页 (非签证页或封底)。",
                        related_material_id=mid,
                        params={"passport_no": pno},
                    ))
                if pno:
                    positives.append("护照号已成功识别")

            # photo size check
            if mtype == "photo":
                # we don't know the pixel dims from this dict — just flag if filename suggests
                fname = (m.get("original_filename") or "").lower()
                if "白底" in fname or "white" in fname:
                    positives.append("白底照片已上传")
                else:
                    issues.append(DiagnoseIssue(
                        code="photo.bg_uncertain",
                        severity="info",
                        title="建议确认照片背景色",
                        detail="多数国家签证要求白底照片,部分东南亚国家接受蓝底。",
                        fix_suggestion="如目标国家是美国/英国/日本/韩国,必须是白底。",
                        related_material_id=mid,
                    ))

            # OCR status
            if m.get("ocr_status") == "failed":
                issues.append(DiagnoseIssue(
                    code=f"ocr.failed.{mtype}",
                    severity="warning",
                    title=f"{_type_label(mtype)} 识别失败",
                    detail="OCR 未能提取字段,签证官在审阅时会消耗更多时间,可能被退回要求重传。",
                    fix_suggestion="请重新上传清晰的扫描件,或检查文件是否损坏。",
                    related_material_id=mid,
                    params={"material_type": mtype},
                ))

        # 3. Field-level cross-checks (form fields)
        if fields:
            travel_date = fields.get("travel_date")
            purpose = fields.get("purpose")
            if not travel_date:
                issues.append(DiagnoseIssue(
                    code="fields.travel_date_missing",
                    severity="warning",
                    title="缺少出行日期",
                    detail="没有出行日期,无法校验护照有效期是否够用。",
                    fix_suggestion="请在表单中填写预计出行日期。",
                ))
            else:
                positives.append(f"已填写出行日期 {travel_date}")
            if not purpose:
                issues.append(DiagnoseIssue(
                    code="fields.purpose_missing",
                    severity="info",
                    title="缺少出行目的",
                    detail="出行目的影响材料清单 (商务签需要邀请函,旅游签需要行程单)。",
                    fix_suggestion="请简要说明: 旅游 / 商务 / 探亲 / 留学。",
                ))
            rule_count += 2

        # 4. RAG context (best-effort, won't fail diagnose)
        policy_refs = self._fetch_policy_refs(country_code, visa_type)

        # 5. Aggregate
        risk_score = sum(_SEVERITY_WEIGHT.get(i.severity, 0.0) for i in issues)
        risk_score = min(1.0, risk_score)

        if risk_score >= 0.5:
            overall_risk = "critical"
        elif risk_score >= 0.3:
            overall_risk = "high"
        elif risk_score >= 0.1:
            overall_risk = "medium"
        else:
            overall_risk = "low"

        summary = self._build_summary(overall_risk, issues, positives, country_code, visa_type)

        # sort issues by severity desc, then by code
        sev_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
        issues.sort(key=lambda i: (sev_order.get(i.severity, 9), i.code))

        return DiagnoseOutput(
            overall_risk=overall_risk,
            risk_score=round(risk_score, 3),
            summary=summary,
            issues=issues,
            positives=positives,
            policy_refs=policy_refs,
            rule_count=rule_count,
        )

    # ------------------------------------------------------------------ #
    # helpers                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _required_for(country_code: str, visa_type: Optional[str]) -> List[Dict[str, Any]]:
        bucket = _REQUIRED.get(country_code)
        if not bucket:
            # unknown country — fall back to a generic minimal checklist
            return [
                {"key": "generic.passport", "types": ["passport"], "reason": "需要有效期 ≥6 个月的护照"},
                {"key": "generic.photo",    "types": ["photo"],    "reason": "需要符合规格的签证照片"},
            ]
        if visa_type and visa_type in bucket:
            return bucket[visa_type]
        return bucket.get("default", [])

    @staticmethod
    def _months_until(date_str: str) -> Optional[int]:
        """Parse YYYY-MM-DD (or YYYY/MM/DD or DD/MM/YYYY) → months from today."""
        if not date_str:
            return None
        s = str(date_str).strip()
        # try ISO first
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y.%m.%d"):
            try:
                d = datetime.strptime(s, fmt).date()
                today = date.today()
                return (d.year - today.year) * 12 + (d.month - today.month) - (1 if d.day < today.day else 0)
            except ValueError:
                continue
        return None

    @staticmethod
    def _looks_like_passport_no(s: str) -> bool:
        s = (s or "").upper().replace(" ", "")
        # most common: 1 letter + 6-9 digits (PRC: E/G/D + 8 digits)
        import re
        return bool(re.match(r"^[A-Z]\d{6,9}$", s))

    def _fetch_policy_refs(self, country_code: str, visa_type: Optional[str]) -> List[str]:
        """Best-effort RAG lookup. Falls back to empty list on any failure."""
        if self._rag is None:
            # cache an async session + retriever lazily
            self._rag = "lazy"  # mark as initialized; actual session created per call
        try:
            import asyncio
            from app.core.db import AsyncSessionLocal
            from app.services.rag.retriever import retrieve

            async def _fetch():
                async with AsyncSessionLocal() as db:
                    query = f"{country_code} {_visa_label(visa_type)} 签证申请所需材料"
                    chunks = await retrieve(
                        db,
                        query=query,
                        country_code=country_code,
                        top_k=3,
                    )
                    refs = []
                    for c in chunks:
                        if c.source_url:
                            refs.append(c.source_url)
                        else:
                            refs.append(c.source_name)
                    return refs

            # run async in sync context (RAG is best-effort, fail soft)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # if we're inside an async context, fall back to a new thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                        return ex.submit(asyncio.run, _fetch()).result()
                else:
                    return loop.run_until_complete(_fetch())
            except RuntimeError:
                return asyncio.run(_fetch())
        except Exception as exc:
            _log.debug(f"RAG policy lookup failed: {exc}")
            return []

    @staticmethod
    def _build_summary(
        overall_risk: str,
        issues: List[DiagnoseIssue],
        positives: List[str],
        country_code: str,
        visa_type: Optional[str],
    ) -> str:
        crit = sum(1 for i in issues if i.severity == "critical")
        err = sum(1 for i in issues if i.severity == "error")
        warn = sum(1 for i in issues if i.severity == "warning")
        dest = _country_name(country_code)
        kind = _visa_label(visa_type)

        if overall_risk == "critical":
            head = f"{dest}{kind}申请存在 {crit} 项关键问题,直接提交大概率被拒签。"
        elif overall_risk == "high":
            head = f"{dest}{kind}申请有 {err} 项必须修复的问题,可能需要补材料。"
        elif overall_risk == "medium":
            head = f"{dest}{kind}申请基本可行,但有 {warn} 项建议优化。"
        else:
            head = f"{dest}{kind}申请材料看起来很完整,可以提交。"

        if positives:
            head += f" 已有 {len(positives)} 项达标。"
        return head


# ---------------------------------------------------------------- #
# i18n label helpers                                                 #
# ---------------------------------------------------------------- #
_COUNTRY_NAMES = {
    "US": "美国", "GB": "英国", "JP": "日本", "KR": "韩国", "SG": "新加坡",
    "TH": "泰国", "VN": "越南", "ID": "印尼", "MY": "马来西亚", "PH": "菲律宾",
    "AU": "澳大利亚", "CA": "加拿大", "DE": "德国", "FR": "法国", "IT": "意大利",
    "ES": "西班牙", "RU": "俄罗斯", "TR": "土耳其", "AE": "阿联酋",
}

_VISA_LABELS = {
    "tourist": "旅游签证",
    "business": "商务签证",
    "student": "留学签证",
    "work": "工作签证",
    "transit": "过境签证",
    "B1": "B1 商务签证",
    "B2": "B2 旅游签证",
    "F1": "F1 留学签证",
}

_TYPE_LABELS = {
    "passport": "护照",
    "id_card": "身份证",
    "household": "户口本",
    "enrollment": "在校证明",
    "photo": "签证照片",
    "form": "申请表",
    "bank": "银行流水",
    "employment": "在职证明/营业执照",
    "hotel": "酒店预订",
    "flight": "机票行程",
    "insurance": "旅行保险",
    "other": "其他材料",
}


def _country_name(code: str) -> str:
    return _COUNTRY_NAMES.get(code.upper(), code.upper())


def _visa_label(vt: Optional[str]) -> str:
    if not vt:
        return ""
    return _VISA_LABELS.get(vt.lower(), vt)


def _type_label(t: str) -> str:
    return _TYPE_LABELS.get(t, t)