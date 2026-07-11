"""Diagnose rule engine — 4 国差异化打分 (旅游签专项, W58)。

入口:
    from app.services.diagnose_rules import compute_diagnose

数据流:
    DiagnoseRequest (form 数据)
      -> compute_diagnose()
        -> 基础项 6 字段 (4 国一致, base.py)
        -> 国家专项 (每个国家一个 config, us/gb/au/schengen)
        -> 合成 (含申根保险硬封顶)
      -> dict(score, level, factors, suggestions, policy_summary)
"""
from __future__ import annotations

from typing import List

from ._types import Factor
from . import _age, _base, _solo_female
from .schengen import schengen_rules
from .us import us_rules
from .gb import gb_rules
from .au import au_rules


_BASE_SCORE = 40
# 申根旅游签保险未购 -> 总分封顶 50 (一票否决型)
_SCHENGEN_INSURANCE_CAP = 50

# 申根国家集合(旅游签统一走申根规则)
_SCHENGEN_COUNTRIES = frozenset({
    "AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO",
    "SK", "SI", "ES", "SE", "CH",
})

# 国家 code -> 专项 rules 路由
_COUNTRY_RULES = {
    "US": us_rules,
    "GB": gb_rules,
    "AU": au_rules,
    "FR": schengen_rules,
}


def _resolve_country_module(country_code: str):
    """申根国都走 schengen_rules, 其余按 code 查表。"""
    cc = (country_code or "").upper()
    if cc in _SCHENGEN_COUNTRIES:
        return schengen_rules, True
    return _COUNTRY_RULES.get(cc), False


def compute_diagnose(req) -> dict:
    """W58: 4 国差异化打分主入口。

    :param req: DiagnoseRequest-like object (有 country_code, marital_status,
                income_bucket, travel_purpose, travel_history, visa_history,
                employment, age, is_solo_female, 以及 W58 新增字段)。
    :return: dict 包含 score, level, factors, suggestions, policy_summary。
    """
    country = (req.country_code or "").upper()
    country_module, is_schengen = _resolve_country_module(country)

    factors: List[Factor] = []

    # ---- 基础项 (4 国一致) ----
    factors.append(_base.score_marital(req.marital_status))
    factors.append(_base.score_income(req.income_bucket))
    factors.append(_base.score_travel_history(req.travel_history))
    factors.append(_base.score_visa_history(req.visa_history))
    factors.append(_base.score_employment(req.employment))

    # ---- 国家专项 ----
    if country_module is not None:
        country_factors = country_module(req)
        # 给专项 factor 标 weight_group="country"
        for f in country_factors:
            f.weight_group = "country"
        factors.extend(country_factors)

    # ---- optional factors (4 国共用逻辑) ----
    solo = _solo_female.score_solo_female(req.is_solo_female, country)
    if solo is not None:
        solo.weight_group = "optional"
        factors.append(solo)

    age_f = _age.score_age(req.age)
    if age_f is not None:
        age_f.weight_group = "optional"
        factors.append(age_f)

    # ---- 合成 ----
    total = _BASE_SCORE + sum(f.impact for f in factors)

    # W58: 申根保险未购 -> 硬封顶 50
    if is_schengen and not getattr(req, "insurance_purchased", False):
        total = min(total, _SCHENGEN_INSURANCE_CAP)

    score = max(0, min(100, total))

    if score >= 75:
        level = "high"
    elif score >= 50:
        level = "medium"
    else:
        level = "low"

    # ---- suggestions: 顶部 3 negative + 顶部 2 positive reinforcement ----
    negatives = sorted([f for f in factors if f.impact < 0], key=lambda x: x.impact)
    positives = sorted([f for f in factors if f.impact > 0], key=lambda x: -x.impact)

    suggestions: list[str] = []
    for f in negatives[:3]:
        suggestions.append(f.detail)
    if not suggestions:
        suggestions.append("您的整体条件良好,建议尽早提交申请,把握时间窗口。")
    for f in positives[:2]:
        suggestions.append(f"✓ {f.name} 是您的加分项,材料中请充分展示。")

    # ---- policy summary ----
    policy_summary = _POLICY_SUMMARY.get(country)
    if policy_summary is None and is_schengen:
        policy_summary = _SCHENGEN_POLICY_SUMMARY

    return {
        "country_code": country,
        "score": score,
        "level": level,
        "factors": factors,
        "suggestions": suggestions,
        "policy_summary": policy_summary,
    }


_POLICY_SUMMARY = {
    "US": "美国 B2 旅游签看重国内约束力(工作/家庭/财产)与面签表现,214b 拒签率与目的真实性高度相关。",
    "GB": "英国 Standard Visitor 旅游签需 UKVCAS 中心递交,签证官重点审核财力证明与签证历史信用。",
    "AU": "澳洲 600 旅游签综合评估财力、签证历史、在职稳定性,首次申请建议附详细行程。",
}
_SCHENGEN_POLICY_SUMMARY = "申根旅游签需行程保险(≥3万欧元医疗) + 逐日行程 + 全程酒店,首次申请必须采集指纹。"
