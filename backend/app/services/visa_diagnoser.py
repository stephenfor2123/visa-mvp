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

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import get_logger
from app.models.material import MATERIAL_TYPES
from app.services.balance_chain_check import check_balance_chain
from app.services.sudden_inflow import detect_sudden_inflows

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
            {"key": "us.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_us_passport"},
            {"key": "us.ds160",      "types": ["form"],       "reason": "需要 DS-160 确认页",      "reason_key": "diagnose.reason_form_ds160"},
            {"key": "us.photo",      "types": ["photo"],      "reason": "需要 51×51mm 白底照片",   "reason_key": "diagnose.reason_us_photo"},
            {"key": "us.financial",  "types": ["other", "bank"], "reason": "建议提供银行流水 / 资产证明", "reason_key": "diagnose.reason_financial_bank"},
            {"key": "us.itinerary",  "types": ["other", "flight", "hotel"], "reason": "建议提供行程单 / 邀请函", "reason_key": "diagnose.reason_itinerary"},
        ],
        "student": [
            {"key": "us.passport",   "types": ["passport"],   "reason": "需要护照",               "reason_key": "diagnose.reason_passport_basic"},
            {"key": "us.ds160",      "types": ["form"],       "reason": "需要 DS-160 确认页",      "reason_key": "diagnose.reason_form_ds160"},
            {"key": "us.i20",        "types": ["form"],       "reason": "需要 I-20 表 (学校签发)", "reason_key": "diagnose.reason_us_i20"},
            {"key": "us.sevis",      "types": ["other"],      "reason": "需要 SEVIS 缴费凭证",     "reason_key": "diagnose.reason_us_sevis"},
            {"key": "us.photo",      "types": ["photo"],      "reason": "需要 51×51mm 白底照片",   "reason_key": "diagnose.reason_us_photo"},
            {"key": "us.financial",  "types": ["other", "bank"], "reason": "需要财力证明",         "reason_key": "diagnose.reason_financial_required"},
        ],
    },
    "VN": {
        "default": [
            {"key": "vn.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "vn.photo",      "types": ["photo"],      "reason": "需要 2 寸白底照片",         "reason_key": "diagnose.reason_vn_photo"},
            {"key": "vn.form",       "types": ["form"],       "reason": "需要签证申请表 (NA1)",      "reason_key": "diagnose.reason_vn_form"},
        ],
    },
    "ID": {
        "default": [
            {"key": "id.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "id.photo",      "types": ["photo"],      "reason": "需要红底或白底 2 寸照片",   "reason_key": "diagnose.reason_id_photo"},
        ],
    },
    "TH": {
        "default": [
            {"key": "th.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "th.photo",      "types": ["photo"],      "reason": "需要 2 寸白底照片",         "reason_key": "diagnose.reason_th_photo"},
            {"key": "th.financial",  "types": ["other", "bank"], "reason": "建议提供财力证明",       "reason_key": "diagnose.reason_financial_suggested"},
        ],
    },
    "JP": {
        "default": [
            {"key": "jp.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "jp.photo",      "types": ["photo"],      "reason": "需要 4.5×4.5cm 白底照片",   "reason_key": "diagnose.reason_jp_photo"},
            {"key": "jp.form",       "types": ["form"],       "reason": "需要签证申请表",           "reason_key": "diagnose.reason_form_required"},
            {"key": "jp.itinerary",  "types": ["other", "flight", "hotel"], "reason": "需要行程单",     "reason_key": "diagnose.reason_itinerary_required"},
            {"key": "jp.financial",  "types": ["other", "bank"], "reason": "需要银行流水",           "reason_key": "diagnose.reason_financial_bank"},
        ],
    },
    "KR": {
        "default": [
            {"key": "kr.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "kr.photo",      "types": ["photo"],      "reason": "需要白底 3.5×4.5cm 照片",  "reason_key": "diagnose.reason_kr_photo"},
            {"key": "kr.form",       "types": ["form"],       "reason": "需要签证申请表",           "reason_key": "diagnose.reason_form_required"},
        ],
    },
    "SG": {
        "default": [
            {"key": "sg.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "sg.photo",      "types": ["photo"],      "reason": "需要白底照片",             "reason_key": "diagnose.reason_sg_photo"},
            {"key": "sg.form",       "types": ["form"],       "reason": "需要申请表 (V14A / V39A)", "reason_key": "diagnose.reason_sg_form"},
        ],
    },
    "GB": {
        "default": [
            {"key": "gb.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "gb.photo",      "types": ["photo"],      "reason": "需要 35×45mm 白底照片",     "reason_key": "diagnose.reason_gb_photo"},
            {"key": "gb.form",       "types": ["form"],       "reason": "需要在线申请表",           "reason_key": "diagnose.reason_form_required"},
            {"key": "gb.financial",  "types": ["other", "bank"], "reason": "需要财力证明",           "reason_key": "diagnose.reason_financial_required"},
        ],
    },
    # W63: AU / CA / NZ — 主要英语国家签证照片均为白底,但 spec 各有微差。
    # spec 措辞按各国移民局官网: AU 35×40mm, CA 35×45mm, NZ 35×45mm。
    "AU": {
        "default": [
            {"key": "au.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "au.photo",      "types": ["photo"],      "reason": "需要 35×40mm 白底照片",     "reason_key": "diagnose.reason_au_photo"},
            {"key": "au.financial",  "types": ["other", "bank"], "reason": "建议提供财力证明",       "reason_key": "diagnose.reason_financial_suggested"},
        ],
    },
    "CA": {
        "default": [
            {"key": "ca.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "ca.photo",      "types": ["photo"],      "reason": "需要 35×45mm 白底照片",     "reason_key": "diagnose.reason_ca_photo"},
        ],
    },
    "NZ": {
        "default": [
            {"key": "nz.passport",   "types": ["passport"],   "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
            {"key": "nz.photo",      "types": ["photo"],      "reason": "需要 35×45mm 白底照片",     "reason_key": "diagnose.reason_nz_photo"},
        ],
    },
    # W63: 申根 26 国共用同一张照片规格 (35×45mm 白底, ICAO 9303 标准)。
    # 按 EU 签证法典统一处理——_REQUIRED 里只为代表性国家(FR/DE/IT/ES/NL)建 rule,
    # 其余申根国通过 _SCHENGEN_COUNTRIES 集合在 _photo_rule_for 里兜底匹配。
}


# W63: 申根 26 国照片规格一致 (35×45mm 白底, ICAO 9303)。给一个公共 spec 字符串,
# 任何申根国家在 _REQUIRED 里没有专属 rule 时都返回这个。
_SCHENGEN_COUNTRIES = frozenset({
    "AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO",
    "SK", "SI", "ES", "SE", "CH",
})
_SCHENGEN_PHOTO_SPEC = "需要 35×45mm 白底照片 (申根标准)"


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
def _issue_refs(m: dict) -> dict:
    """Map diagnose issue back to a stored material id or wizard item_key."""
    item_key = m.get("item_key")
    mid = m.get("id")
    if item_key:
        return {"related_item_key": str(item_key), "related_material_id": None}
    return {
        "related_material_id": mid if isinstance(mid, int) else None,
        "related_item_key": None,
    }


@dataclass
class DiagnoseIssue:
    code: str
    severity: str
    title: str
    detail: str
    fix_suggestion: Optional[str] = None
    related_material_id: Optional[int] = None
    related_item_key: Optional[str] = None
    # W39: raw values behind the zh-CN title/detail strings above, so a
    # frontend can re-render the message in the user's own locale via its
    # own i18n keyed by `code` instead of showing this server's zh-CN text.
    # W46: also include i18n keys + structured params so the frontend can
    # look up `title_key` / `detail_key` / `fix_key` and render via vue-i18n.
    title_key: Optional[str] = None
    detail_key: Optional[str] = None
    fix_key: Optional[str] = None
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
        # W63-h: 把 order 上的 form 字段和行程字段也算成"已具备"的虚拟 material_type。
        # 之前: DS-160 / 行程单在 materials-wizard 里是用户手填的 form / 行程字段,
        # 不会产生 material record,导致 _required_for 永远报"缺少"。
        # 修法:从 fields 里反推 present_types
        if fields:
            f = {k.lower(): v for k, v in (fields or {}).items() if v not in (None, "", [])}
            # DS-160 关键字段任一填写 → 算 form 已具备
            ds160_keys = {"surname", "given_name", "passport_no", "date_of_birth", "nationality",
                          "purpose_of_trip", "us_specific"}
            if ds160_keys & set(f.keys()):
                present_types.add("form")
            # 行程单关键字段任一填写 → 算 flight/hotel 已具备
            # (兼容 OrderNew.vue 拼 payload 用的字段名: arrival_date / departure_date
            #  而不是 travel_date 体系)
            if any(f.get(k) for k in (
                "depart_date", "return_date", "departure_date", "arrival_date",
                "destination", "flight_no", "hotel_name", "itinerary_text",
            )):
                present_types.add("flight")
                present_types.add("hotel")
                present_types.add("itinerary")
        for req in required:
            if not any(t in present_types for t in req["types"]):
                # W46: build i18n-friendly params. The frontend will look up
                # `diagnose.missing_required_title` / `diagnose.missing_required_fix`
                # and use `country`/`visa`/`types` for interpolation. We also
                # include `reason_key` so the `detail` (a per-country rule
                # reason) can be re-rendered via i18n.
                issues.append(DiagnoseIssue(
                    code=req["key"],
                    severity="warning",
                    title=f"缺少{_country_name(country_code)}{_visa_label(visa_type)}申请必备材料",
                    title_key="diagnose.missing_required_title",
                    detail=req["reason"],
                    detail_key=req.get("reason_key"),
                    fix_suggestion=f"请补充: {', '.join(_type_label(t) for t in req['types'])}",
                    fix_key="diagnose.missing_required_fix",
                    params={
                        "country": country_code,
                        "visa": visa_type or "",
                        "types": ", ".join(_type_label(t) for t in req["types"]),
                        # stash the material type tokens so en/id/vi can rebuild
                        # the fix label from `diagnose.type_<token>` keys instead of
                        # the hardcoded Chinese comma-list
                        "type_tokens": list(req["types"]),
                    },
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
                            title_key="diagnose.passport_not_detected_title",
                            detail="OCR 没有从这张图片里识别出任何护照特征（页眉、MRZ 码等），签证官会要求补交或直接拒签。",
                            detail_key="diagnose.passport_not_detected_detail",
                            fix_suggestion="请确认上传的是清晰、完整的护照资料页,不是户口本、照片或其他证件。",
                            fix_key="diagnose.passport_not_detected_fix",
                            **_issue_refs(m),
                        ))
                    else:
                        issues.append(DiagnoseIssue(
                            code="passport.expiry_missing",
                            severity="error",
                            title="护照有效期字段缺失",
                            title_key="diagnose.passport_expiry_missing_title",
                            detail="OCR 未识别到护照有效期,签证官会要求补交或直接拒签。",
                            detail_key="diagnose.passport_expiry_missing_detail",
                            fix_suggestion="请上传清晰的护照首页扫描件,或手动填写有效期字段。",
                            fix_key="diagnose.passport_expiry_missing_fix",
                            **_issue_refs(m),
                        ))
                else:
                    months_left = self._months_until(expiry)
                    if months_left is not None and months_left < self.PASSPORT_MIN_VALIDITY_MONTHS:
                        issues.append(DiagnoseIssue(
                            code="passport.expiry_short",
                            severity="critical",
                            title=f"护照有效期不足 {self.PASSPORT_MIN_VALIDITY_MONTHS} 个月",
                            title_key="diagnose.passport_expiry_short_title",
                            detail=f"有效期 {expiry},剩余约 {months_left} 个月,大多数国家要求 ≥6 个月。",
                            detail_key="diagnose.passport_expiry_short_detail",
                            fix_suggestion="出发前必须续期护照,否则会被直接拒签。",
                            fix_key="diagnose.passport_expiry_short_fix",
                            **_issue_refs(m),
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
                        title_key="diagnose.passport_no_suspicious_title",
                        detail=f"识别到的护照号 {pno!r} 不符合常见格式 (1 字母 + 7-8 位数字)。",
                        detail_key="diagnose.passport_no_suspicious_detail",
                        fix_suggestion="请确认上传的是护照资料页 (非签证页或封底)。",
                        fix_key="diagnose.passport_no_suspicious_fix",
                        **_issue_refs(m),
                        params={"passport_no": pno},
                    ))
                if pno:
                    positives.append("护照号已成功识别")

            # bank statement checks (W51) — 看 ocr_result 里是否解析出 transactions
            if mtype == "bank":
                rule_count += 1
                # bank_statement_parser 写进 ocr_result 的字段:
                #   transactions, monthly_summary, coverage_months, txn_count,
                #   monthly_income_avg, monthly_expense_avg, ending_balance,
                #   large_inflows, large_outflows, parser, confidence
                parser_used = (ocr_fields.get("parser") or "").lower()
                txn_count = int(ocr_fields.get("txn_count") or 0)
                coverage_months = int(ocr_fields.get("coverage_months") or 0)
                monthly_income = ocr_fields.get("monthly_income_avg")
                large_inflows = ocr_fields.get("large_inflows") or []

                # 1) 流水根本解析不出来 — 提示用户人工补
                if parser_used in ("", "none") or txn_count == 0:
                    issues.append(DiagnoseIssue(
                        code="bank.unparseable",
                        severity="warning",
                        title="银行流水未能结构化解析",
                        title_key="diagnose.bank_unparseable_title",
                        detail="OCR 识别到了内容,但没能从中提取出结构化交易明细 (transactions=0)。签证官看不到具体收入/支出,可能被退回要求补材料。",
                        detail_key="diagnose.bank_unparseable_detail",
                        fix_suggestion="请确认上传的是清晰的银行流水 PDF/截图(近 3 个月),或切换上传其他银行的电子流水。",
                        fix_key="diagnose.bank_unparseable_fix",
                        **_issue_refs(m),
                    ))
                else:
                    if parser_used == "regex":
                        positives.append(f"银行流水已识别 {txn_count} 条交易 (规则解析)")
                    else:
                        positives.append(f"银行流水已识别 {txn_count} 条交易 (AI 解析)")

                # W53 余额链检查 (P0): 抓篡改和缺页
                # A 方案: balance 覆盖率 < 30% 不报 critical,只 info
                transactions = ocr_fields.get("transactions") or []
                if transactions:
                    chain = check_balance_chain(transactions)
                    if chain["ok"] is False:
                        # 断链: critical 或 warn 取决于断链笔数
                        for f in chain["findings"]:
                            issues.append(DiagnoseIssue(
                                code=f.code,
                                severity=f.severity,
                                title=f.title,
                                title_key="diagnose.bank_balance_chain_title",
                                detail=f.detail,
                                detail_key="diagnose.bank_balance_chain_detail",
                                fix_suggestion=f.fix_suggestion or "",
                                fix_key="diagnose.bank_balance_chain_fix",
                                **_issue_refs(m),
                                params=f.evidence or {},
                            ))
                    elif chain["ok"] is True:
                        positives.append(f"余额链连续性校验通过 (覆盖 {chain['coverage']:.0%})")
                    # ok=None 是低覆盖率,info 级别不强制暴露 — 但保留日志
                    else:
                        positives.append(f"余额字段覆盖率 {chain['coverage']:.0%},无法做余额链审核")

                # 2) 流水覆盖期 < 3 个月
                if coverage_months > 0 and coverage_months < 3:
                    issues.append(DiagnoseIssue(
                        code="bank.coverage_short",
                        severity="warning",
                        title=f"银行流水仅覆盖 {coverage_months} 个月",
                        title_key="diagnose.bank_coverage_short_title",
                        detail=f"识别出来的交易横跨 {coverage_months} 个月,大多数使馆建议提供最近 3-6 个月的银行流水,以评估经济稳定性。",
                        detail_key="diagnose.bank_coverage_short_detail",
                        fix_suggestion="请上传近 3-6 个月的银行流水(含本月),或合并多份不同月份的截图。",
                        fix_key="diagnose.bank_coverage_short_fix",
                        **_issue_refs(m),
                        params={"months": coverage_months},
                    ))
                elif coverage_months >= 3:
                    positives.append(f"银行流水覆盖 {coverage_months} 个月")

                # 3) 月均收入异常低(若有数据)
                if monthly_income is not None and monthly_income < 3000:
                    issues.append(DiagnoseIssue(
                        code="bank.income_low",
                        severity="warning",
                        title="月均收入偏低",
                        title_key="diagnose.bank_income_low_title",
                        detail=f"识别到的月均收入约 ¥{monthly_income:,.0f},签证官通常会要求补充存款证明或资助信。",
                        detail_key="diagnose.bank_income_low_detail",
                        fix_suggestion="建议同步上传:存款证明 / 房产证 / 资助人收入证明。",
                        fix_key="diagnose.bank_income_low_fix",
                        **_issue_refs(m),
                        params={"monthly_income": round(monthly_income, 2)},
                    ))

                # 4) 大额异常资金流入
                if large_inflows:
                    sample = large_inflows[0]
                    issues.append(DiagnoseIssue(
                        code="bank.large_inflow",
                        severity="warning",
                        title=f"识别到 {len(large_inflows)} 笔大额异常转入",
                        title_key="diagnose.bank_large_inflow_title",
                        detail=f"如 ¥{sample['amount']:,.0f} ({sample.get('date')}, {sample.get('description', '')}) 等大额转入,签证官可能怀疑是临时存款而非稳定收入。",
                        detail_key="diagnose.bank_large_inflow_detail",
                        fix_suggestion="若是亲友赠予或一次性大额,建议在面试时主动解释资金来源并提供证明材料。",
                        fix_key="diagnose.bank_large_inflow_fix",
                        **_issue_refs(m),
                        params={"count": len(large_inflows)},
                    ))

                # 5) W52: 工资断档 — 找连续无 income 的月份段,提示用户解释资金来源
                income_gaps = ocr_fields.get("income_gaps") or []
                if income_gaps:
                    # 取最大的一段(gap_months 最大的)作为示例
                    worst = max(income_gaps, key=lambda g: g.get("gap_months", 0))
                    gap_months_count = worst.get("gap_months", 0)
                    start = worst.get("start_month", "")
                    end = worst.get("end_month", "")
                    # 多少段 (>=1 就提示)
                    if gap_months_count >= 1:
                        title = f"银行流水出现 {gap_months_count} 个月工资断档" if gap_months_count == 1 else f"银行流水出现连续 {gap_months_count} 个月无工资入账"
                        detail = f"识别出 {gap_months_count} 个月({start} → {end})未收到任何工资/入账记录,签证官可能质疑经济稳定性。"
                        issues.append(DiagnoseIssue(
                            code="bank.income_gap",
                            severity="warning",
                            title=title,
                            title_key="diagnose.bank_income_gap_title",
                            detail=detail,
                            detail_key="diagnose.bank_income_gap_detail",
                            fix_suggestion="若是换工作/失业,建议提供:离职证明、新公司 offer、补贴信 (资助人/家人);若是留学/休学,提供在读证明。",
                            fix_key="diagnose.bank_income_gap_fix",
                            **_issue_refs(m),
                            params={
                                "gap_months": gap_months_count,
                                "start_month": start,
                                "end_month": end,
                                "gap_count": len(income_gaps),
                            },
                        ))

                # 6) W54: 月份缺失 — monthly_summary 月份不连续(可能是缺页或 PS)
                missing_months = ocr_fields.get("missing_months") or []
                if missing_months:
                    issues.append(DiagnoseIssue(
                        code="bank.months_missing",
                        severity="warning",
                        title=f"银行流水月份不连续,缺 {len(missing_months)} 个月",
                        title_key="diagnose.bank_months_missing_title",
                        detail=(
                            f"识别的月份 {missing_months[0]} → {missing_months[-1]} 之间存在缺月 "
                            f"({', '.join(missing_months[:5])}{'...' if len(missing_months) > 5 else ''})。"
                            f"可能是多页拼接时漏页,或对方银行该月未出流水。"
                        ),
                        detail_key="diagnose.bank_months_missing_detail",
                        fix_suggestion="请核对原始流水是否齐全,或上传一份连续 3-6 个月的银行流水。",
                        fix_key="diagnose.bank_months_missing_fix",
                        **_issue_refs(m),
                        params={"missing_months": missing_months},
                    ))

                # 7) W55: 突击存入检测 (时序规则)
                #   - 申请前 30 天突然大额转入,且之前 90 天余额/收入都低
                #   - 满足 → severity 升级到 hard_block / high / warn
                sudden = detect_sudden_inflows(transactions)
                if sudden:
                    # 取最严重的一笔
                    _rank = {"warn": 0, "high": 1, "hard_block": 2}
                    top = max(sudden, key=lambda s: _rank.get(s.severity, 0))
                    # 写进 ocr_fields 方便下游 (前端报告) 拿
                    ocr_fields["sudden_inflows"] = [
                        {
                            "date": s.date, "amount": s.amount,
                            "description": s.description, "page": s.page,
                            "severity": s.severity, "reason": s.reason,
                        }
                        for s in sudden
                    ]
                    # 报 issue(取最严重的一笔作为代表)
                    issues.append(DiagnoseIssue(
                        code="bank.sudden_inflow",
                        severity=top.severity,
                        title=(
                            f"识别到 {len(sudden)} 笔突击存入(签证官最忌)"
                            if len(sudden) > 1 else
                            "识别到一笔突击存入(签证官最忌)"
                        ),
                        title_key="diagnose.bank_sudden_inflow_title",
                        detail=(
                            f"如 {top.date} 的 ¥{top.amount:,.0f} ({top.description or '无描述'}): {top.reason}。"
                            f"签证官可能怀疑是临时凑的余额,而非稳定收入。"
                        ),
                        detail_key="diagnose.bank_sudden_inflow_detail",
                        fix_suggestion=(
                            "若是亲友赠予或一次性进账,建议:1) 在面试时主动解释资金来源; "
                            "2) 同步上传赠予人的资金证明 / 转账记录; "
                            "3) 提供更早几个月的银行流水佐证长期稳定收入。"
                        ),
                        fix_key="diagnose.bank_sudden_inflow_fix",
                        **_issue_refs(m),
                        params={
                            "count": len(sudden),
                            "top_date": top.date,
                            "top_amount": top.amount,
                            "top_severity": top.severity,
                            "samples": [
                                {"date": s.date, "amount": s.amount, "severity": s.severity}
                                for s in sudden[:5]
                            ],
                        },
                    ))

                # 8) W54: 余额换算 + 达标判定(可选 — 仅当 caller 提供 fields["destination"] 时)
                destination = (fields or {}).get("destination") if fields else None
                if destination:
                    try:
                        from app.services.financial_standard import (
                            evaluate_balance,
                            get_financial_standard,
                        )
                        std = get_financial_standard(
                            source_country=(ocr_fields.get("source_country") or "CN"),
                            destination=destination,
                        )
                        stay_days = fields.get("stay_days") if fields else None
                        ending = ocr_fields.get("ending_balance")
                        verdict = evaluate_balance(
                            ending_balance_src=ending,
                            source_country=(ocr_fields.get("source_country") or "CN"),
                            destination=destination,
                            stay_days=stay_days,
                        )
                        # 仅在 block/warn 时报 issue;info 静默
                        if verdict.severity in ("block", "warn"):
                            issues.append(DiagnoseIssue(
                                code="bank.balance_below_threshold",
                                severity=verdict.severity,
                                title=(
                                    f"余额不满足 {destination} 签证财务要求"
                                    if std.hard_block else
                                    f"余额低于 {destination} 签证建议"
                                ),
                                title_key="diagnose.bank_balance_threshold_title",
                                detail=verdict.detail,
                                detail_key="diagnose.bank_balance_threshold_detail",
                                fix_suggestion=(
                                    "建议补充:存款证明 / 资助信 / 流水余额更高的月份截图。"
                                    if std.hard_block else
                                    "建议补一份余额证明(银行盖章)以增加签证官信任度。"
                                ),
                                fix_key="diagnose.bank_balance_threshold_fix",
                                **_issue_refs(m),
                                params={
                                    "ending_balance_src": verdict.ending_balance_src,
                                    "ending_balance_dest": verdict.ending_balance_dest,
                                    "daily_min_dest": verdict.daily_min_dest,
                                    "min_coverage_months": std.min_coverage_months,
                                    "hard_block": std.hard_block,
                                },
                            ))
                    except Exception as exc:  # noqa: BLE001
                        _log.warning("balance threshold check failed: %s", exc)

            # photo size check (W62: country-aware)
            if mtype == "photo":
                # we don't know the pixel dims from this dict — use filename as a
                # best-effort hint, BUT the actual spec must follow the destination
                # country's rule (e.g. US 51×51mm 白底, ID 红/白二选一).
                fname = (m.get("original_filename") or "").lower()
                fname_says_white = ("白底" in fname) or ("white" in fname)
                fname_says_red = ("红底" in fname) or ("red" in fname)
                fname_says_blue = ("蓝底" in fname) or ("blue" in fname)
                photo_rule = self._photo_rule_for(country_code, visa_type)
                if fname_says_white:
                    positives.append("白底照片已上传")
                if photo_rule:
                    # country has a specific photo spec — use it, mention destination.
                    # Only flag if filename clearly contradicts the country's rule
                    # (e.g. user picked US and named the file "红底.jpg"). Otherwise
                    # just give a calm "please confirm" hint that names the spec.
                    contradicts = False
                    if photo_rule["color"] == "白底" and (fname_says_red or fname_says_blue):
                        contradicts = True
                    elif photo_rule["color"] == "红底" and (fname_says_white or fname_says_blue):
                        contradicts = True
                    if contradicts:
                        issues.append(DiagnoseIssue(
                            code="photo.bg_mismatch",
                            severity="error",
                            title=f"{_country_name(country_code)}签证照片背景色不符",
                            title_key="diagnose.photo_bg_mismatch_title",
                            detail=f"目的国 {_country_name(country_code)} 要求{photo_rule['spec']}。文件名提示上传的是 {'红底' if fname_says_red else '蓝底'}照片,可能直接导致拒签。",
                            detail_key="diagnose.photo_bg_mismatch_detail",
                            fix_suggestion=f"请重新拍摄 {photo_rule['spec']} 后再上传,不要用手机自拍,建议去专业签证照相馆。",
                            fix_key="diagnose.photo_bg_mismatch_fix",
                            **_issue_refs(m),
                            params={"country": country_code, "spec": photo_rule["spec"]},
                        ))
                    else:
                        issues.append(DiagnoseIssue(
                            code="photo.bg_uncertain",
                            severity="info",
                            title=f"请确认照片符合 {_country_name(country_code)} 规格",
                            title_key="diagnose.photo_bg_country_title",
                            detail=f"目的国 {_country_name(country_code)} 要求{photo_rule['spec']}。系统无法从图片中识别背景色,请确认上传的照片是合规规格后再提交。",
                            detail_key="diagnose.photo_bg_country_detail",
                            fix_suggestion=f"重新拍摄 {photo_rule['spec']} 后再上传,或去专业签证照相馆一次性拍对。",
                            fix_key="diagnose.photo_bg_country_fix",
                            **_issue_refs(m),
                            params={"country": country_code, "spec": photo_rule["spec"]},
                        ))
                # W63: photo_rule 为 None 时(国家没在 _REQUIRED + _SCHENGEN_COUNTRIES 里),
                # 完全静默,不再吐"多数国家白底,部分东南亚蓝底"的模糊提示。
                # 用户反馈:这种通用提示对去美/英/澳/申根的人没意义,反而让人误以为蓝底也可以。

            # OCR status
            if m.get("ocr_status") == "failed":
                issues.append(DiagnoseIssue(
                    code=f"ocr.failed.{mtype}",
                    severity="warning",
                    title=f"{_type_label(mtype)} 识别失败",
                    title_key="diagnose.ocr_failed_title",
                    detail="OCR 未能提取字段,签证官在审阅时会消耗更多时间,可能被退回要求重传。",
                    detail_key="diagnose.ocr_failed_detail",
                    fix_suggestion="请重新上传清晰的扫描件,或检查文件是否损坏。",
                    fix_key="diagnose.ocr_failed_fix",
                    **_issue_refs(m),
                    params={"material_type": mtype},
                ))

        # 3. Field-level cross-checks (form fields)
        if fields:
            # W63-h: 兼容 OrderNew 拼的 payload 字段名(arrival_date / departure_date
            # 而非 travel_date),以及 itinerary_text 也算"有出行日期"
            travel_date = (
                fields.get("travel_date")
                or fields.get("depart_date")
                or fields.get("arrival_date")
                or fields.get("departure_date")
            )
            purpose = (
                fields.get("purpose")
                or fields.get("purpose_of_trip")
            )
            # W63-h: 行程单 / 机票 / 酒店任一已具备时,默认目的 = tourism (旅游)。
            # 用户在 materials-wizard 里填了 days[] + city + hotel 就是"已规划旅游行程",
            # 此时再报"缺少出行目的"是误报 — 让 purpose 自动从行程单反推。
            if not purpose and (
                fields.get("itinerary_text")
                or fields.get("flight_no")
                or fields.get("hotel_name")
                or fields.get("destination")
            ):
                purpose = "tourism"
            if not travel_date:
                issues.append(DiagnoseIssue(
                    code="fields.travel_date_missing",
                    severity="warning",
                    title="缺少出行日期",
                    title_key="diagnose.travel_date_missing_title",
                    detail="没有出行日期,无法校验护照有效期是否够用。",
                    detail_key="diagnose.travel_date_missing_detail",
                    fix_suggestion="请在表单中填写预计出行日期。",
                    fix_key="diagnose.travel_date_missing_fix",
                ))
            else:
                positives.append(f"已填写出行日期 {travel_date}")
            if not purpose:
                issues.append(DiagnoseIssue(
                    code="fields.purpose_missing",
                    severity="info",
                    title="缺少出行目的",
                    title_key="diagnose.purpose_missing_title",
                    detail="出行目的影响材料清单 (商务签需要邀请函,旅游签需要行程单)。",
                    detail_key="diagnose.purpose_missing_detail",
                    fix_suggestion="请简要说明: 旅游 / 商务 / 探亲 / 留学。",
                    fix_key="diagnose.purpose_missing_fix",
                ))
            rule_count += 2

            # 3.5 W52: 余额 vs 行程预算 — ending_balance 够不够覆盖行程花费。
            # 行程预算 = 机票 + 酒店天数 × 单价 + 餐食(¥200/天默认) + 杂费
            # 我们不强求精确,粗估一个"够用/不够"判断。
            stay_days = _coerce_int(fields.get("stay_days"))
            flight_no = fields.get("flight_no")
            hotel_name = fields.get("hotel_name")
            if stay_days is not None and stay_days > 0:
                # 预算粗估: 机票 ¥6000 (国际) + 酒店 ¥800/天 + 餐 ¥200/天 + 杂 ¥100/天
                # 简化到 4 个变量,用户有填 flight_no / hotel_name 加分(认为"有规划"→ 略宽松)
                # 没有 flight_no/hotel_name 视作"未确认具体行程",要求余额更高
                base_flight = 6000 if flight_no else 8000  # 没填机票 → 视作最坏情况
                daily_hotel = 800
                daily_food = 200
                daily_misc = 100
                budget_total = base_flight + stay_days * (daily_hotel + daily_food + daily_misc)
                # 找 ending_balance(从所有 bank materials 的 ocr_result 取最大那个)
                max_ending_balance = None
                for bm in materials:
                    if (bm.get("material_type") or "").lower() != "bank":
                        continue
                    bm_ocr = bm.get("ocr_result") or {}
                    eb = bm_ocr.get("ending_balance")
                    if eb is not None:
                        try:
                            eb_f = float(eb)
                            if max_ending_balance is None or eb_f > max_ending_balance:
                                max_ending_balance = eb_f
                        except (TypeError, ValueError):
                            pass
                if max_ending_balance is not None:
                    ratio = max_ending_balance / max(budget_total, 1)
                    if ratio < 1.0:
                        issues.append(DiagnoseIssue(
                            code="bank.balance_coverage",
                            severity="warning",
                            title=f"余额不足以覆盖行程预算",
                            title_key="diagnose.bank_balance_coverage_title",
                            detail=f"识别到的账户余额约 ¥{max_ending_balance:,.0f},按 {stay_days} 天行程粗估预算约 ¥{budget_total:,.0f} (机票+酒店+餐食+杂费),余额 < 预算,签证官可能怀疑支付能力。",
                            detail_key="diagnose.bank_balance_coverage_detail",
                            fix_suggestion="建议补充存款证明 / 资产证明 (房/车/理财),或缩短行程 / 降低酒店规格。",
                            fix_key="diagnose.bank_balance_coverage_fix",
                            params={
                                "ending_balance": round(max_ending_balance, 2),
                                "budget_total": round(budget_total, 2),
                                "ratio": round(ratio, 2),
                                "stay_days": stay_days,
                            },
                        ))
                    elif ratio < 2.0:
                        positives.append(f"账户余额约覆盖行程预算 {ratio:.1f} 倍 (建议 ≥2 倍)")
                    else:
                        positives.append(f"账户余额约覆盖行程预算 {ratio:.1f} 倍,资金充裕")
                    rule_count += 1

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

        # W63-h: 去重 — 同一份材料(related_material_id 相同)报同 code 只保留一条;
        # related_material_id 为空的全局 issue(如 fields.* missing)按 code 唯一保留。
        # 真因: 用户订单 materialIds 里可能出现重复 ID(上传多次同一份),
        # 之前会重复触发 bank.months_missing / bank.coverage_short 等 per-material issue。
        seen = set()
        deduped_issues = []
        for iss in issues:
            key = (iss.code, iss.related_material_id or "")
            if key in seen:
                continue
            seen.add(key)
            deduped_issues.append(iss)
        issues = deduped_issues

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
                {"key": "generic.passport", "types": ["passport"], "reason": "需要有效期 ≥6 个月的护照", "reason_key": "diagnose.reason_passport_6m"},
                {"key": "generic.photo",    "types": ["photo"],    "reason": "需要符合规格的签证照片",     "reason_key": "diagnose.reason_photo_basic"},
            ]
        if visa_type and visa_type in bucket:
            return bucket[visa_type]
        return bucket.get("default", [])

    @staticmethod
    def _photo_rule_for(country_code: str, visa_type: Optional[str]) -> Optional[Dict[str, str]]:
        """W62 / W63: extract the destination country's photo spec so the
        photo-bg check can say "美国签证要求 51×51mm 白底照片" instead of the
        generic "多数国家白底,部分东南亚蓝底" hint.

        Returns None ONLY when the country has no specific photo rule
        (so caller shows nothing — user asked for "no rule, no prompt").
        For Schengen states without their own entry, falls back to the
        shared Schengen spec (35×45mm white).
        """
        # Try visa-specific bucket first, then default
        bucket = _REQUIRED.get(country_code) or {}
        rules = bucket.get(visa_type or "", []) if visa_type else []
        if not rules:
            rules = bucket.get("default", [])
        for r in rules:
            if "photo" in r.get("types", []) or r.get("key", "").endswith(".photo"):
                reason = r.get("reason", "")
                # detect dominant color keyword
                color = None
                for kw in ("白底", "红底", "蓝底"):
                    if kw in reason:
                        color = kw
                        break
                if not color:
                    return None
                return {"spec": reason, "color": color}
        # W63: Schengen fallback — 26 申根国共用同一规格
        if (country_code or "").upper() in _SCHENGEN_COUNTRIES:
            return {"spec": _SCHENGEN_PHOTO_SPEC, "color": "白底"}
        return None

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


def _coerce_int(value: Any) -> Optional[int]:
    """把表单字段里的"5"/"5 天"/5 各种形式都规整成 int,失败返 None。"""
    if value is None:
        return None
    if isinstance(value, bool):  # bool 是 int 子类,单独处理
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    # 去掉"天"/"日"等中英文后缀
    m = re.match(r"^(\d+)", s)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _country_name(code: str) -> str:
    return _COUNTRY_NAMES.get(code.upper(), code.upper())


def _visa_label(vt: Optional[str]) -> str:
    if not vt:
        return ""
    return _VISA_LABELS.get(vt.lower(), vt)


def _type_label(t: str) -> str:
    return _TYPE_LABELS.get(t, t)