"""/api/v2/diagnose — visa eligibility quick-check (rule engine over personal profile).

Input:  country + personal profile (marital, income, travel history, visa history, employment, age, purpose).
Output: 0-100 score + level (high|medium|low) + risk factors + suggestions.

Public endpoint — no auth required (it's a pre-screening tool, not a binding assessment).
"""
from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/diagnose", tags=["diagnose"])


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #
class DiagnoseRequest(BaseModel):
    country_code: str = Field(..., min_length=1, max_length=8, description="US / JP / KR / SG / FR / GB / TH / VN / ID")
    # 婚姻
    marital_status: str = Field(..., description="single | married | divorced | widowed")
    # 收入分档 (人民币月收入)
    income_bucket: str = Field(..., description="below_5k | 5k_15k | 15k_30k | 30k_100k | above_100k")
    # 出行目的
    travel_purpose: str = Field(..., description="business | tourism | family | study | other")
    # 出行记录 (过去5年)
    travel_history: str = Field(..., description="none | 1_3 | 4_10 | above_10")
    # 签证历史
    visa_history: str = Field(..., description="none | 1_2 | above_2")
    # 在职状态
    employment: str = Field(..., description="employed | freelancer | student | retired | unemployed")
    # 年龄 (可选, 20-70)
    age: Optional[int] = Field(None, ge=10, le=90)
    # 是否单身女性独自旅行 (新加坡/韩国 FAQ 提到)
    is_solo_female: bool = False


class FactorOut(BaseModel):
    name: str
    impact: int  # -100 to +100
    detail: str
    category: str  # positive | negative | neutral


class DiagnoseOut(BaseModel):
    country_code: str
    score: int
    level: str  # high | medium | low
    factors: List[FactorOut]
    suggestions: List[str]
    policy_summary: Optional[str] = None


# --------------------------------------------------------------------------- #
# Rule engine                                                                 #
# --------------------------------------------------------------------------- #
_BASE_SCORE = 60  # everyone starts here


def _score_income(bucket: str) -> FactorOut:
    table = {
        "above_100k": (25, "高收入人群,财务约束力强,签证官最关心的稳定性指标。"),
        "30k_100k":   (15, "中上收入,具备稳定还款/家庭责任能力。"),
        "15k_30k":    (5,  "中等收入,在材料充分情况下通常可达标。"),
        "5k_15k":     (-10, "收入偏低,建议提供存款证明或资产证明补充。"),
        "below_5k":   (-20, "收入过低,需提供额外财力证明(存款/房产/资助信)。"),
    }
    score, detail = table[bucket]
    label_map = {"above_100k": "高收入", "30k_100k": "中上收入", "15k_30k": "中等收入", "5k_15k": "偏低收入", "below_5k": "低收入"}
    return FactorOut(name=f"收入:{label_map[bucket]}", impact=score, detail=detail, category="positive" if score >= 0 else "negative")


def _score_marital(status: str) -> FactorOut:
    table = {
        "married":  (5,  "已婚,家庭约束力强,签证官通常视为稳定因素。"),
        "single":   (0,  "单身无负担,在材料充分时不影响判断。"),
        "divorced": (0,  "离异,需说明独立出行目的。"),
        "widowed":  (0,  "丧偶,材料完整性更重要。"),
    }
    score, detail = table[status]
    label_map = {"married": "已婚", "single": "未婚", "divorced": "离异", "widowed": "丧偶"}
    return FactorOut(name=f"婚姻:{label_map[status]}", impact=score, detail=detail, category="neutral" if score == 0 else "positive")


def _score_travel_history(hist: str) -> FactorOut:
    table = {
        "above_10": (20, "丰富出行记录,签证官认为出行习惯已稳定,信任度高。"),
        "4_10":     (12, "中等出行记录,具备基本国际旅行经验。"),
        "1_3":      (3,  "少量出行记录,建议附上过往签证页/出入境章。"),
        "none":     (-5, "无出行记录,首次申请建议提供详细行程和国内约束力证明。"),
    }
    score, detail = table[hist]
    label_map = {"above_10": "10+ 次", "4_10": "4-10 次", "1_3": "1-3 次", "none": "无记录"}
    return FactorOut(name=f"出行记录:{label_map[hist]}", impact=score, detail=detail, category="positive" if score >= 0 else "negative")


def _score_visa_history(hist: str) -> FactorOut:
    table = {
        "above_2": (10, "已持有 3+ 次签证,签证官倾向于快速通过。"),
        "1_2":     (5,  "已有 1-2 次签证记录,有助于通过率。"),
        "none":    (-3, "无签证历史,首次申请是中性偏弱项。"),
    }
    score, detail = table[hist]
    label_map = {"above_2": "3+ 次", "1_2": "1-2 次", "none": "无签证记录"}
    return FactorOut(name=f"签证历史:{label_map[hist]}", impact=score, detail=detail, category="positive" if score >= 0 else "negative")


def _score_employment(emp: str) -> FactorOut:
    table = {
        "employed":   (10, "在职,有稳定雇主约束力,加分项。"),
        "freelancer": (-5, "自由职业者,建议附合作合同/银行流水证明稳定收入。"),
        "student":    (0,  "学生身份,需提供在读证明和父母资助材料。"),
        "retired":    (5,  "退休,有稳定退休金/养老金是加分项。"),
        "unemployed": (-15,"无业状态,签证官最关注,需充分解释资金来源。"),
    }
    score, detail = table[emp]
    label_map = {"employed": "在职", "freelancer": "自由职业", "student": "学生", "retired": "退休", "unemployed": "无业"}
    return FactorOut(name=f"在职:{label_map[emp]}", impact=score, detail=detail, category="positive" if score >= 0 else "negative")


def _score_purpose(purpose: str, country: str) -> FactorOut:
    """Country-specific nuance (e.g. US B1/B2 strongly values clear business purpose)."""
    label_map = {"business": "商务", "tourism": "旅游", "family": "探亲", "study": "留学", "other": "其他"}
    if country in ("US",) and purpose == "business":
        return FactorOut(name=f"出行目的:{label_map[purpose]}", impact=8, detail="美国签证看重明确商务目的与邀请函,纯商务行程信任度高。", category="positive")
    if country in ("GB",) and purpose == "study":
        return FactorOut(name=f"出行目的:{label_map[purpose]}", impact=5, detail="英国学生签证路径成熟,需 CAS letter。", category="positive")
    if country in ("TH", "VN", "ID") and purpose == "tourism":
        return FactorOut(name=f"出行目的:{label_map[purpose]}", impact=5, detail="东南亚国家旅游签材料相对简单,通过率高。", category="positive")
    if purpose == "other":
        return FactorOut(name=f"出行目的:{label_map[purpose]}", impact=-5, detail="目的不明确,签证官可能要求补充说明,建议具体化。", category="negative")
    return FactorOut(name=f"出行目的:{label_map[purpose]}", impact=0, detail="中性项,材料齐全即可。", category="neutral")


def _score_solo_female(solo: bool, country: str) -> Optional[FactorOut]:
    if not solo:
        return None
    # 新加坡/韩国 FAQ 提到单身女性独自旅行可能拒签
    if country in ("SG", "KR"):
        return FactorOut(
            name="单身女性独自旅行",
            impact=-8,
            detail=f"{country} 签证对单身女性独自旅行审核更严,建议附亲属关系证明或同行人资料。",
            category="negative",
        )
    return FactorOut(
        name="单身女性独自旅行",
        impact=-3,
        detail="少数国家审核更严,建议提供行程详细规划与国内约束力证明。",
        category="negative",
    )


def _score_age(age: Optional[int]) -> Optional[FactorOut]:
    if age is None:
        return None
    if 30 <= age <= 50:
        return FactorOut(name=f"年龄:{age}岁", impact=3, detail="30-50 岁是签证最稳定人群,工作/家庭约束力都强。", category="positive")
    if age < 25:
        return FactorOut(name=f"年龄:{age}岁", impact=-3, detail="25 岁以下年轻单身申请者,签证官可能要求更多财力证明。", category="negative")
    if age > 60:
        return FactorOut(name=f"年龄:{age}岁", impact=-2, detail="60 岁以上需提供体检报告和旅行保险(部分国家要求)。", category="negative")
    return None


# --------------------------------------------------------------------------- #
# Policy summary (RAG-coupled: country-specific)                               #
# --------------------------------------------------------------------------- #
_COUNTRY_POLICY = {
    "US": "美国 B1/B2 看重国内约束力(工作/家庭/财产),214b 拒签率与目的真实性高度相关。",
    "FR": "申根签证需行程保险(≥3万欧元),首次申请必须采集指纹。",
    "JP": "日本签证需指定旅行社代送,经济材料(流水/纳税/存款)三选一。",
    "KR": "韩国 C-3 签证 5 年多次需年收入 ≥ 6 万或存款 50 万。",
    "SG": "新加坡 e-Visa 拒签常见原因:单身女性/流水不足/目的不明。",
    "GB": "英国 Standard Visitor 6 个月有效,需 UKVCAS 中心递交。",
    "TH": "泰国免签 30 天(2024 起中国公民),如需更长停留可办 TR/EDU 签证。",
    "VN": "越南 e-visa 25 美元,审批 3 个工作日,有效期最长 90 天。",
    "ID": "印尼 B211A 50 美元,e-VOA 在线申请,1-3 个工作日出签。",
}


# --------------------------------------------------------------------------- #
# Endpoint                                                                    #
# --------------------------------------------------------------------------- #
@router.post(
    "",
    response_model=ApiResponse[DiagnoseOut],
    summary="Visa eligibility quick-check (rule engine)",
)
async def diagnose(body: DiagnoseRequest) -> ApiResponse[DiagnoseOut]:
    factors: List[FactorOut] = []
    factors.append(_score_marital(body.marital_status))
    factors.append(_score_income(body.income_bucket))
    factors.append(_score_travel_history(body.travel_history))
    factors.append(_score_visa_history(body.visa_history))
    factors.append(_score_employment(body.employment))
    factors.append(_score_purpose(body.travel_purpose, body.country_code.upper()))

    optional_factors = [
        _score_solo_female(body.is_solo_female, body.country_code.upper()),
        _score_age(body.age),
    ]
    for f in optional_factors:
        if f is not None:
            factors.append(f)

    # Sum
    total = _BASE_SCORE + sum(f.impact for f in factors)
    score = max(0, min(100, total))

    if score >= 75:
        level = "high"
        level_cn = "高"
    elif score >= 50:
        level = "medium"
        level_cn = "中"
    else:
        level = "low"
        level_cn = "低"

    # Suggestions: derived from top negative factors
    negatives = sorted([f for f in factors if f.impact < 0], key=lambda x: x.impact)
    suggestions: List[str] = []
    for f in negatives[:3]:
        suggestions.append(f.detail)
    if not suggestions:
        suggestions.append("您的整体条件良好,建议尽早提交申请,把握时间窗口。")

    # Top 3 positive reinforcement
    positives = sorted([f for f in factors if f.impact > 0], key=lambda x: -x.impact)
    for f in positives[:2]:
        suggestions.append(f"✓ {f.name} 是您的加分项,材料中请充分展示。")

    policy_summary = _COUNTRY_POLICY.get(body.country_code.upper())

    return ApiResponse[DiagnoseOut](
        code="1000",
        message="OK",
        data=DiagnoseOut(
            country_code=body.country_code.upper(),
            score=score,
            level=level,
            factors=factors,
            suggestions=suggestions,
            policy_summary=policy_summary,
        ),
    )
