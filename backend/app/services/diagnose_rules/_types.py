"""W58 内部 factor 容器 (dataclass, 不依赖 pydantic)。

主流程 app.api.v2.diagnose.compute_diagnose() 会把它转成 pydantic FactorOut
再返回给前端。这样 rules 包零依赖, 易于单测。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class Factor:
    name: str
    impact: int
    detail: str
    category: Literal["positive", "negative", "neutral"]
    # weight_group: base | country | optional — 标记 factor 来源, 方便前端按组显示
    weight_group: str = "base"
