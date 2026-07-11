"""W58 单身女性独自旅行 — 适用国家扩到 US/FR(不仅是 SG/KR)。

理由: 实际美签/申根旅游签都看这个风险因子(美签 214b 单身年轻女性拒签率高,
申根签证官也会关注独行安全), 原版只覆盖 SG/KR 不够。
"""
from __future__ import annotations

from typing import Optional

from ._types import Factor


# W58: 严格档(签证官明确重点关注)
_STRICT_COUNTRIES = frozenset({"SG", "KR", "US"})
# 申根国家(签证官一般性关注)
_SCHENGEN_COUNTRIES = frozenset({
    "AT", "BE", "BG", "HR", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "RO",
    "SK", "SI", "ES", "SE", "CH",
})


def score_solo_female(solo: bool, country: str) -> Optional[Factor]:
    if not solo:
        return None
    cc = (country or "").upper()
    if cc in _STRICT_COUNTRIES:
        return Factor(
            name="单身女性独自旅行",
            impact=-8,
            detail=f"{cc} 签证对单身女性独自旅行审核更严,建议附亲属关系证明或同行人资料。",
            category="negative",
        )
    if cc in _SCHENGEN_COUNTRIES:
        return Factor(
            name="单身女性独自旅行",
            impact=-5,
            detail="申根签证对单身女性独自旅行会多问行程安排与回国约束力,建议附详细行程和国内亲属信息。",
            category="negative",
        )
    return Factor(
        name="单身女性独自旅行",
        impact=-3,
        detail="少数国家审核更严,建议提供行程详细规划与国内约束力证明。",
        category="negative",
    )
