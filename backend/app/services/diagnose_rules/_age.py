"""W58 年龄分段 — 4 国共用(可选, age=None 时不出 factor)。"""
from __future__ import annotations

from typing import Optional

from ._types import Factor


def score_age(age: Optional[int]) -> Optional[Factor]:
    if age is None:
        return None
    if 30 <= age <= 50:
        return Factor(
            name=f"年龄:{age}岁",
            impact=3,
            detail="30-50 岁是签证最稳定人群,工作/家庭约束力都强。",
            category="positive",
        )
    if age < 25:
        return Factor(
            name=f"年龄:{age}岁",
            impact=-3,
            detail="25 岁以下年轻单身申请者,签证官可能要求更多财力证明。",
            category="negative",
        )
    if age > 60:
        return Factor(
            name=f"年龄:{age}岁",
            impact=-2,
            detail="60 岁以上需提供体检报告和旅行保险(部分国家要求)。",
            category="negative",
        )
    return None
