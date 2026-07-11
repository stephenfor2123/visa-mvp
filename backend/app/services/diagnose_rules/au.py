"""W58 🇦🇺 澳洲 600 旅游签专项。

核心:
- 资金状况: 3-6 个月稳定流水 + 余额 > 3 万加分
- 签证历史(发达国家): 有美/英/加/申根签证 +5, 仅有东南亚 0, 无 -3
- 在职稳定性: 同公司 > 2 年 +3, 自由职业/无业 -3
- 行程: 有 +3, 无 -3(澳签也看行程真实性)

依赖 req 上 W58 新增字段:
    funds_balance_bucket (str|None)        — "above_3w" | "1w_3w" | "below_1w"
    developed_country_visa (str|None)     — "us_gb_schengen" | "other" | "none"
    employment_years (int|None)
    employment (str)                      — 自由职业/无业判断
    itinerary_complete (str|None)         — "full" | "none" | None
"""
from __future__ import annotations

from typing import List

from ._types import Factor


def au_rules(req) -> List[Factor]:
    factors: List[Factor] = []

    # 1) 资金状况(澳签标准比英签略低, 3 万)
    funds = getattr(req, "funds_balance_bucket", None)
    if funds == "above_3w":
        factors.append(Factor(
            name="资金:余额 > 3 万 + 稳定流水",
            impact=5,
            detail="3-6 个月稳定流水 + 余额 > 3 万,澳签财力达标。",
            category="positive",
        ))
    elif funds == "below_1w":
        factors.append(Factor(
            name="资金:余额 < 1 万",
            impact=-5,
            detail="余额偏低,签证官会怀疑支付能力。",
            category="negative",
        ))
    # 1w_3w 中性, 不出 factor

    # 2) 签证历史(发达国家)
    dev_visa = getattr(req, "developed_country_visa", None)
    if dev_visa == "us_gb_schengen":
        factors.append(Factor(
            name="签证历史:有美/英/申根签证",
            impact=5,
            detail="持有过美/英/申根签证,信用记录好,澳签信任度高。",
            category="positive",
        ))
    elif dev_visa == "other":
        factors.append(Factor(
            name="签证历史:有其他发达国家签证",
            impact=3,
            detail="持有过其他发达国家签证(加/日/韩/新等),有一定信用记录。",
            category="positive",
        ))
    elif dev_visa == "none":
        factors.append(Factor(
            name="签证历史:无发达国家签证",
            impact=-3,
            detail="首次申请发达国家签证,签证官会重点审核材料。",
            category="negative",
        ))

    # 3) 在职稳定性
    years = getattr(req, "employment_years", None)
    employment = getattr(req, "employment", None)
    if years is not None and years > 2:
        factors.append(Factor(
            name="在职稳定性:> 2 年",
            impact=3,
            detail="同公司 > 2 年,签证官认为稳定性强。",
            category="positive",
        ))
    elif employment in ("freelancer", "unemployed"):
        factors.append(Factor(
            name="在职:自由职业/无业",
            impact=-3,
            detail="自由职业/无业签证官会重点关注,需补合作合同/资助信。",
            category="negative",
        ))

    # 4) 行程
    itinerary = getattr(req, "itinerary_complete", None)
    if itinerary == "full":
        factors.append(Factor(
            name="行程:有详细行程",
            impact=3,
            detail="详细行程是澳签旅游的真实性加分项。",
            category="positive",
        ))
    elif itinerary == "none":
        factors.append(Factor(
            name="行程:缺失",
            impact=-3,
            detail="无行程签证官会质疑访问目的。",
            category="negative",
        ))

    return factors
