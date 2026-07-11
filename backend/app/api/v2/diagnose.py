"""/api/v2/diagnose — visa eligibility quick-check (rule engine over personal profile).

W58: 4 国差异化打分(旅游签专项)。
  - 基础项 6 字段 (4 国一致) — _base.py
  - 国家专项 — us.py / gb.py / au.py / schengen.py
  - optional — _age.py / _solo_female.py

Input:  country + 6 基础字段 + W58 扩展字段(国内约束力/在职年限/保险/资金覆盖比/...)
Output: 0-100 score + level (high|medium|low) + risk factors + suggestions.

Public endpoint — no auth required (it's a pre-screening tool, not a binding assessment).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.services.diagnose_rules import compute_diagnose

router = APIRouter(prefix="/diagnose", tags=["diagnose"])


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #
class DiagnoseRequest(BaseModel):
    country_code: str = Field(..., min_length=1, max_length=8, description="US / GB / AU / FR(及申根 26 国) / JP / KR / SG / TH / VN / ID")
    # 婚姻
    marital_status: str = Field(..., description="single | married | divorced | widowed")
    # 收入分档 (人民币月收入)
    income_bucket: str = Field(..., description="below_5k | 5k_15k | 15k_30k | 30k_100k | above_100k")
    # 出行目的(旅游签专项已收口, 但保留字段以兼容其他产品线)
    travel_purpose: str = Field("tourism", description="tourism (W58 收口为旅游签)")
    # 出行记录 (过去5年)
    travel_history: str = Field(..., description="none | 1_3 | 4_10 | above_10")
    # 签证历史
    visa_history: str = Field(..., description="none | 1_2 | above_2")
    # 在职状态
    employment: str = Field(..., description="employed | freelancer | student | retired | unemployed")
    # 年龄 (可选, 20-70)
    age: Optional[int] = Field(None, ge=10, le=90)
    # 是否单身女性独自旅行
    is_solo_female: bool = False

    # ---- W58 新增字段 (可选, 不传则不参与该项打分) ----
    # 国内约束力 — 有房/有车/有存款的项数 (0~3)
    property_signals: Optional[int] = Field(None, ge=0, le=3)
    # 资金来源类型
    income_source: Optional[str] = Field(None, description="salary | one_off")
    # 面签准备度(美签专项)
    interview_ready: Optional[str] = Field(None, description="ready | unprepared")
    # 资金余额分档(英/澳签)
    funds_balance_bucket: Optional[str] = Field(None, description="above_5w | 1w_5w | above_3w | below_1w")
    # 在职年限
    employment_years: Optional[int] = Field(None, ge=0, le=50)
    # 英国签证历史
    uk_visa_history: Optional[str] = Field(None, description="clean | overstayed | never")
    # 发达国家签证历史
    developed_country_visa: Optional[str] = Field(None, description="us_gb_schengen | other | none")
    # 行程完整度
    itinerary_complete: Optional[str] = Field(None, description="full | partial | none")
    # 申根保险已购
    insurance_purchased: Optional[bool] = Field(None)
    # 资金覆盖比(余额 / 行程预算)
    funds_coverage_ratio: Optional[float] = Field(None, ge=0)
    # 5 年内申根指纹
    schengen_fingerprint_5y: Optional[bool] = Field(None)
    # 准假信已开
    leave_letter_ready: Optional[bool] = Field(None)


class FactorOut(BaseModel):
    name: str
    impact: int  # -100 to +100
    detail: str
    category: str  # positive | negative | neutral
    weight_group: str = "base"  # base | country | optional


class DiagnoseOut(BaseModel):
    country_code: str
    score: int
    level: str  # high | medium | low
    factors: List[FactorOut]
    suggestions: List[str]
    policy_summary: Optional[str] = None


# --------------------------------------------------------------------------- #
# Endpoint                                                                    #
# --------------------------------------------------------------------------- #
@router.post(
    "",
    response_model=ApiResponse[DiagnoseOut],
    summary="Visa eligibility quick-check (rule engine, W58 4 国差异化)",
)
async def diagnose(body: DiagnoseRequest) -> ApiResponse[DiagnoseOut]:
    result = compute_diagnose(body)

    # dataclass Factor -> pydantic FactorOut
    factors_out = [
        FactorOut(
            name=f.name,
            impact=f.impact,
            detail=f.detail,
            category=f.category,
            weight_group=f.weight_group,
        )
        for f in result["factors"]
    ]

    return ApiResponse[DiagnoseOut](
        code="1000",
        message="OK",
        data=DiagnoseOut(
            country_code=result["country_code"],
            score=result["score"],
            level=result["level"],
            factors=factors_out,
            suggestions=result["suggestions"],
            policy_summary=result["policy_summary"],
        ),
    )

