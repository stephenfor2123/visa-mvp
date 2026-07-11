"""W58 🇬🇧 英国 Standard Visitor(旅游签)专项。

核心:
- 资金充足度(无公开线但实际看): 流水余额 > 5 万加分, < 1 万减分
- 在职年限(同公司): > 3 年加分, < 1 年减分
- 英国签证历史: clean +5, overstayed -8(黑历史)
- 行程+酒店: 完整 +5, 缺 -3(英签旅游也看行程真实性)

依赖 req 上 W58 新增字段:
    funds_balance_bucket (str|None)  — "above_5w" | "1w_5w" | "below_1w"
    employment_years (int|None)
    uk_visa_history (str|None)        — "clean" | "overstayed" | "never"
    itinerary_complete (str|None)     — "full" | "partial" | "none"
"""
from __future__ import annotations

from typing import List

from ._types import Factor


def gb_rules(req) -> List[Factor]:
    factors: List[Factor] = []

    # 1) 资金充足度
    funds = getattr(req, "funds_balance_bucket", None)
    if funds == "above_5w":
        factors.append(Factor(
            name="资金:流水余额 > 5 万",
            impact=5,
            detail="6 个月稳定流水 + 余额 > 5 万,英签无公开最低线但实际看财力。",
            category="positive",
        ))
    elif funds == "1w_5w":
        pass  # 中性, 不出 factor
    elif funds == "below_1w":
        factors.append(Factor(
            name="资金:流水余额 < 1 万",
            impact=-5,
            detail="余额偏低,签证官可能怀疑支付能力,建议补充存款证明。",
            category="negative",
        ))

    # 2) 在职年限
    years = getattr(req, "employment_years", None)
    if years is not None:
        if years > 3:
            factors.append(Factor(
                name="在职年限:> 3 年",
                impact=3,
                detail="同公司 > 3 年,签证官认为稳定性强。",
                category="positive",
            ))
        elif years < 1:
            factors.append(Factor(
                name="在职年限:< 1 年",
                impact=-3,
                detail="跳槽频繁或刚入职,签证官可能质疑工作真实性。",
                category="negative",
            ))

    # 3) 英国签证历史
    uk_hist = getattr(req, "uk_visa_history", None)
    if uk_hist == "clean":
        factors.append(Factor(
            name="英国签证历史:无逾期",
            impact=5,
            detail="有过英国签证且无逾期,签证官信任度高。",
            category="positive",
        ))
    elif uk_hist == "overstayed":
        factors.append(Factor(
            name="英国签证历史:有过逾期",
            impact=-8,
            detail="英国签证逾期是黑历史,新申请会被严格审核,建议附详细解释信。",
            category="negative",
        ))

    # 4) 行程 + 酒店
    itinerary = getattr(req, "itinerary_complete", None)
    if itinerary == "full":
        factors.append(Factor(
            name="行程:完整 + 全程酒店",
            impact=5,
            detail="英签旅游也看行程真实性,完整行程 + 酒店预订单是加分项。",
            category="positive",
        ))
    elif itinerary == "partial":
        factors.append(Factor(
            name="行程:不完整",
            impact=-3,
            detail="缺酒店或行程模糊,签证官会质疑访问目的真实性。",
            category="negative",
        ))
    elif itinerary == "none":
        factors.append(Factor(
            name="行程:缺失",
            impact=-5,
            detail="无行程无酒店,英签旅游签会被退回要求补材料。",
            category="negative",
        ))

    return factors
