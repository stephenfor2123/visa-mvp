"""W58 🇺🇸 美国 B2 旅游签专项。

核心:
- 国内约束力(有房/有车/有存款)是签证官最看重的"会回来"信号
- 年龄+婚姻组合: 25-40 单身年轻是 214b 高危人群
- 资金来源类型: 工资性 vs 一次性大额入账
- 面签准备度: 行程/工作/资金/回国理由自洽 → +5, 未准备 → -5

依赖 req 上 W58 新增字段:
    has_property (bool|None)   — 有房/有车/有存款(任一项, 兜底字段)
    property_signals (int)     — 有几项(0~3): 房/车/存款
    age (int|None)             — 25-40 单身年轻判断
    marital_status (str)
    income_source (str|None)   — "salary" | "one_off" | None
    interview_ready (str|None) — "ready" | "unprepared" | None
"""
from __future__ import annotations

from typing import List

from ._types import Factor


def us_rules(req) -> List[Factor]:
    factors: List[Factor] = []

    # 1) 国内约束力强信号
    property_signals = getattr(req, "property_signals", None)
    if property_signals is not None:
        if property_signals >= 2:
            factors.append(Factor(
                name="国内约束力:有房/有车/有存款(任2项)",
                impact=5,
                detail="美签最看重'会回来'的信号,有 2 项以上固定资产/存款,签证官信任度高。",
                category="positive",
            ))
        elif property_signals == 1:
            # 1 项 = 中性, 不出 factor
            pass
        else:  # 0
            factors.append(Factor(
                name="国内约束力:无固定资产/存款",
                impact=-5,
                detail="无房/无车/无存款,签证官会重点关注回国意愿,建议在面签时充分说明。",
                category="negative",
            ))

    # 2) 年龄 + 婚姻组合
    age = getattr(req, "age", None)
    marital = getattr(req, "marital_status", None)
    if age is not None and 25 <= age <= 40:
        if marital == "single":
            factors.append(Factor(
                name="风险人群:25-40 单身年轻",
                impact=-5,
                detail="美签 214b 单身年轻申请者拒签率显著高,建议在面签时突出工作稳定性和国内约束力。",
                category="negative",
            ))
        elif marital == "married":
            factors.append(Factor(
                name="加分组合:25-40 已婚",
                impact=3,
                detail="已婚,签证官认为移民倾向低,家庭约束力强。",
                category="positive",
            ))

    # 3) 资金来源类型
    income_source = getattr(req, "income_source", None)
    if income_source == "salary":
        factors.append(Factor(
            name="资金来源:工资性收入",
            impact=3,
            detail="工资性收入可解释,签证官会认为经济稳定。",
            category="positive",
        ))
    elif income_source == "one_off":
        factors.append(Factor(
            name="资金来源:大额一次性入账",
            impact=-3,
            detail="一次性大额入账签证官会重点问询,建议在面签时主动解释来源。",
            category="negative",
        ))

    # 4) 面签准备度
    interview_ready = getattr(req, "interview_ready", None)
    if interview_ready == "ready":
        factors.append(Factor(
            name="面签准备:充分",
            impact=5,
            detail="行程/工作/资金/回国理由自洽,面签通过率显著提升。",
            category="positive",
        ))
    elif interview_ready == "unprepared":
        factors.append(Factor(
            name="面签准备:不足",
            impact=-5,
            detail="美签 1-3 分钟问 1-2 个关键问题,准备不足易触发拒签。",
            category="negative",
        ))

    return factors
