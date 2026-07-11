"""W58 基础项 — 4 国 100% 一致的 6 字段打分。

字段:
- marital_status (4 档)
- income_bucket (5 档, 单位:人民币/月 — i18n 层做文案替换)
- travel_history (4 档)
- visa_history (3 档)
- employment (5 档)
"""
from __future__ import annotations

from ._types import Factor


def score_marital(status: str) -> Factor:
    table = {
        "married":  (3,  "已婚,家庭约束力强,签证官通常视为稳定因素。", "positive"),
        "single":   (0,  "单身无负担,在材料充分时不影响判断。", "neutral"),
        "divorced": (0,  "离异,需说明独立出行目的。", "neutral"),
        "widowed":  (0,  "丧偶,材料完整性更重要。", "neutral"),
    }
    score, detail, cat = table[status]
    label_map = {"married": "已婚", "single": "未婚", "divorced": "离异", "widowed": "丧偶"}
    return Factor(
        name=f"婚姻:{label_map[status]}",
        impact=score,
        detail=detail,
        category=cat,
    )


def score_income(bucket: str) -> Factor:
    table = {
        "above_100k": (20, "高收入人群,财务约束力强,签证官最关心的稳定性指标。", "positive"),
        "30k_100k":   (12, "中上收入,具备稳定还款/家庭责任能力。", "positive"),
        "15k_30k":    (5,  "中等收入,在材料充分情况下通常可达标。", "positive"),
        "5k_15k":     (-8, "收入偏低,建议提供存款证明或资产证明补充。", "negative"),
        "below_5k":   (-15, "收入过低,需提供额外财力证明(存款/房产/资助信)。", "negative"),
    }
    score, detail, cat = table[bucket]
    label_map = {
        "above_100k": "高收入", "30k_100k": "中上收入", "15k_30k": "中等收入",
        "5k_15k": "偏低收入", "below_5k": "低收入",
    }
    return Factor(
        name=f"收入:{label_map[bucket]}",
        impact=score,
        detail=detail,
        category=cat,
    )


def score_travel_history(hist: str) -> Factor:
    table = {
        "above_10": (15, "丰富出行记录,签证官认为出行习惯已稳定,信任度高。", "positive"),
        "4_10":     (9,  "中等出行记录,具备基本国际旅行经验。", "positive"),
        "1_3":      (3,  "少量出行记录,建议附上过往签证页/出入境章。", "positive"),
        "none":     (-3, "无出行记录,首次申请建议提供详细行程和国内约束力证明。", "negative"),
    }
    score, detail, cat = table[hist]
    label_map = {"above_10": "10+ 次", "4_10": "4-10 次", "1_3": "1-3 次", "none": "无记录"}
    return Factor(
        name=f"出行记录:{label_map[hist]}",
        impact=score,
        detail=detail,
        category=cat,
    )


def score_visa_history(hist: str) -> Factor:
    table = {
        "above_2": (8,  "已持有 3+ 次签证,签证官倾向于快速通过。", "positive"),
        "1_2":     (4,  "已有 1-2 次签证记录,有助于通过率。", "positive"),
        "none":    (-2, "无签证历史,首次申请是中性偏弱项。", "negative"),
    }
    score, detail, cat = table[hist]
    label_map = {"above_2": "3+ 次", "1_2": "1-2 次", "none": "无签证记录"}
    return Factor(
        name=f"签证历史:{label_map[hist]}",
        impact=score,
        detail=detail,
        category=cat,
    )


def score_employment(emp: str) -> Factor:
    table = {
        "employed":   (8,  "在职,有稳定雇主约束力,加分项。", "positive"),
        "freelancer": (-3, "自由职业者,建议附合作合同/银行流水证明稳定收入。", "negative"),
        "student":    (0,  "学生身份,需提供在读证明和父母资助材料。", "neutral"),
        "retired":    (4,  "退休,有稳定退休金/养老金是加分项。", "positive"),
        "unemployed": (-10, "无业状态,签证官最关注,需充分解释资金来源。", "negative"),
    }
    score, detail, cat = table[emp]
    label_map = {
        "employed": "在职", "freelancer": "自由职业", "student": "学生",
        "retired": "退休", "unemployed": "无业",
    }
    return Factor(
        name=f"在职:{label_map[emp]}",
        impact=score,
        detail=detail,
        category=cat,
    )
