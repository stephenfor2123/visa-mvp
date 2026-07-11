"""W58 🇫🇷🇩🇪🇮🇹 申根旅游签专项(26 国共用)。

核心(申根旅游签最严的 3 件套):
- 行程完整度(权重最大): 完整 +8 / 缺 -5 / 完全没 -15
- 保险(一票否决型, 由 __init__ 硬封顶 50 配合, 这里额外 -20 显式扣分)
- 资金覆盖度: 余额 > 行程预算 × 1.5 +5, 不足 -5
- 首次申根: 5 年内有指纹 +3, 首次 -3
- 在职+准假: 准假信齐 +3, 缺 -3

依赖 req 上 W58 新增字段:
    itinerary_complete (str|None)     — "full" | "partial" | "none"
    insurance_purchased (bool)        — 申根保险是否已购
    funds_coverage_ratio (float|None) — 余额 / 行程预算(>1.5 加分, <1 减分)
    schengen_fingerprint_5y (bool)    — 5 年内申根指纹
    employment (str)                  — 在职判断
    leave_letter_ready (bool|None)    — 准假信是否已开
"""
from __future__ import annotations

from typing import List

from ._types import Factor


def schengen_rules(req) -> List[Factor]:
    factors: List[Factor] = []

    # 1) 行程完整度(权重最大)
    itinerary = getattr(req, "itinerary_complete", None)
    if itinerary == "full":
        factors.append(Factor(
            name="行程:逐日行程 + 全程酒店 + 往返机票齐全",
            impact=8,
            detail="申根旅游签最看重行程完整性,逐日行程 + 酒店 + 机票齐全是核心加分项。",
            category="positive",
        ))
    elif itinerary == "partial":
        factors.append(Factor(
            name="行程:缺酒店或机票",
            impact=-5,
            detail="缺酒店或机票预订单,申根签证官会退回要求补材料。",
            category="negative",
        ))
    elif itinerary == "none":
        factors.append(Factor(
            name="行程:完全缺失",
            impact=-15,
            detail="无行程无酒店无机票,申根旅游签基本必拒。",
            category="negative",
        ))

    # 2) 保险(显式扣分, 硬封顶由 __init__ 处理)
    insurance = getattr(req, "insurance_purchased", False)
    if insurance:
        factors.append(Factor(
            name="保险:已购 ≥ €3 万医疗保险",
            impact=5,
            detail="申根强制要求医疗保险覆盖全程(≥ €3 万),已购买是基础门槛。",
            category="positive",
        ))
    else:
        factors.append(Factor(
            name="保险:未购申根医疗保险",
            impact=-20,
            detail="申根强制医疗保险,未购买会被直接拒签。",
            category="negative",
        ))

    # 3) 资金覆盖度
    ratio = getattr(req, "funds_coverage_ratio", None)
    if ratio is not None:
        if ratio >= 1.5:
            factors.append(Factor(
                name="资金:覆盖行程预算 ≥ 1.5 倍",
                impact=5,
                detail="流水余额 > 行程预算 × 1.5,申根'日均 €60-100'隐含线达标。",
                category="positive",
            ))
        elif ratio < 1.0:
            factors.append(Factor(
                name="资金:不足覆盖行程预算",
                impact=-5,
                detail="余额 < 行程预算,签证官会怀疑支付能力。",
                category="negative",
            ))
        # 1.0-1.5 中性, 不出 factor

    # 4) 5 年内申根指纹
    fp_5y = getattr(req, "schengen_fingerprint_5y", None)
    if fp_5y is True:
        factors.append(Factor(
            name="指纹:5 年内已录",
            impact=3,
            detail="5 年内录过申根指纹,免录,流程简化。",
            category="positive",
        ))
    elif fp_5y is False:
        factors.append(Factor(
            name="指纹:首次申请需录",
            impact=-3,
            detail="首次申根必须到 VFS 中心录指纹,流程多且更严。",
            category="negative",
        ))

    # 5) 在职 + 准假信
    leave_ready = getattr(req, "leave_letter_ready", None)
    employment = getattr(req, "employment", None)
    if employment == "employed":
        if leave_ready is True:
            factors.append(Factor(
                name="在职证明 + 准假信:齐全",
                impact=3,
                detail="在职证明 + 准假信齐全,签证官认为回国约束力强。",
                category="positive",
            ))
        elif leave_ready is False:
            factors.append(Factor(
                name="在职:缺准假信",
                impact=-3,
                detail="在职但缺准假信,签证官会怀疑是否真回去。",
                category="negative",
            ))

    return factors
