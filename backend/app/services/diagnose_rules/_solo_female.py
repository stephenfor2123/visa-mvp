"""W58 单身女性独自旅行 — 产品线 US / GB / AU / Schengen。"""
from __future__ import annotations

from typing import Optional

from ._types import Factor


# 严格档: 美签 214(b) 对单身年轻女性关注度最高
_STRICT_COUNTRIES = frozenset({"US", "GB", "AU"})
# 申根国家(一般性关注)
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
    # Outside product scope — no score (destination should have been rejected upstream)
    return None
