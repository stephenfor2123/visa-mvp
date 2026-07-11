"""突击存入检测 (sudden inflow) — W55

设计稿定位
----------
签证官最忌的"临时凑余额"信号:
    申请前 N 天突然出现大额转入,之前长期余额/收入都低。

跟 parser 现有 `large_inflows` 的区别:
    - large_inflows: 只看单笔金额是否 > 阈值(每个大额都标)
    - sudden_inflows: 看时序模式 — 单笔金额大 + 之前余额/收入都低 +
                      时间靠近"申请日"(假定最近一笔或最近 N 天)

策略 (W55 v1 规则版,P2 上 LLM 解释)
-----------------------------------
对每笔 in-direction 交易,计算 4 个信号:
    1. 单笔金额 >= 阈值(走 locale["large_threshold"])
    2. 该笔之前 90 天平均余额 < 该笔金额 × 0.5
       (之前的余额明显不够,大额进账"突然"把它撑起来)
    3. 该笔之前 90 天月均收入 < 该笔金额 × 0.3
       (不是正常工资,是临时凑的)
    4. 该笔距离最近一笔 in 不超过 30 天 (相对"近期"窗口)

满足全部 4 条 → 标记为 sudden_inflow,severity:
    - hard_block: 该笔金额 > 之前余额 × 5 (极度异常)
    - high:       该笔金额 > 之前余额 × 3
    - warn:       其他

返回
----
@dataclass SuddenInflow:
    txn_idx: int
    date: str
    amount: float
    description: Optional[str]
    page: Optional[int]
    pre_avg_balance_90d: Optional[float]
    pre_avg_income_90d: Optional[float]
    severity: str  # hard_block|high|warn
    reason: str
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# 阈值                                                                #
# ---------------------------------------------------------------- #
# 突击存入的"窗口期"(往前看多少天算"之前")
WINDOW_DAYS = 90

# 单笔金额相对"之前平均"的倍数 — 触发条件
RATIO_TO_PRE_BALANCE_BLOCK = 5.0   # 单笔 > 之前 90d 平均余额 × 5 -> hard_block
RATIO_TO_PRE_BALANCE_HIGH = 3.0    # 单笔 > 之前 90d 平均余额 × 3 -> high
RATIO_TO_PRE_INCOME_WARN = 0.3     # 之前 90d 月均收入 < 单笔 × 0.3 -> warn

# 距最近一笔 in 的天数(超过这个不认为"近期")
RECENT_INFLOW_DAYS = 30


# ---------------------------------------------------------------- #
# 数据结构                                                            #
# ---------------------------------------------------------------- #
@dataclass
class SuddenInflow:
    """一笔突击存入。"""
    txn_idx: int
    date: str
    amount: float
    description: Optional[str] = None
    page: Optional[int] = None
    pre_avg_balance_90d: Optional[float] = None
    pre_avg_income_90d: Optional[float] = None
    severity: str = "warn"   # hard_block|high|warn
    reason: str = ""


# ---------------------------------------------------------------- #
# 主检查                                                              #
# ---------------------------------------------------------------- #
def detect_sudden_inflows(
    transactions: List[Dict[str, Any]],
    *,
    window_days: int = WINDOW_DAYS,
    recent_days: int = RECENT_INFLOW_DAYS,
) -> List[SuddenInflow]:
    """从 transactions 找突击存入(in 方向 + 时序异常)。

    Args:
        transactions: [{date, amount, balance, direction, page?}, ...]
                       必须含 date (YYYY-MM-DD) + amount + direction
                       balance 字段可选(没 balance 也能跑,只是信号 #2 给 None)
        window_days: 算"之前"的窗口(默认 90 天)
        recent_days: 距"申请日"<= 多少天算近期(默认 30 天,这里用"距最后一笔 in"近似)

    Returns:
        SuddenInflow 列表(按日期升序)
    """
    if not transactions:
        return []

    # 排序(按日期 + 原始顺序)
    sorted_txns = sorted(enumerate(transactions), key=lambda x: (x[1].get("date") or "", x[0]))

    # 找出所有 in-direction 交易
    in_txns = [(i, t) for i, t in sorted_txns if t.get("direction") == "in" and t.get("date")]
    if not in_txns:
        return []

    # 申请日近似 = 最后一笔 in 的日期(银行流水通常最新一笔就是申请前)
    apply_date_str = in_txns[-1][1]["date"]
    try:
        apply_date = date.fromisoformat(apply_date_str)
    except (ValueError, TypeError):
        return []

    sudden_list: List[SuddenInflow] = []

    for orig_idx, t in in_txns:
        try:
            tx_date = date.fromisoformat(t["date"])
        except (ValueError, TypeError):
            continue
        amount = float(t.get("amount") or 0)
        if amount <= 0:
            continue

        # 窗口起: 该笔之前 window_days 天的交易
        window_start = tx_date - timedelta(days=window_days)
        pre_txns = [
            (i, pt) for i, pt in sorted_txns
            if pt.get("date") and window_start <= _to_date(pt["date"]) < tx_date
        ]

        # 信号 #1: 单笔金额(本身已是 in,这里只用作 ratio 计算的基准)
        # 信号 #2: 之前 window_days 内的"平均余额"(有 balance 字段才算)
        pre_balances = [
            float(pt["balance"]) for _, pt in pre_txns
            if pt.get("balance") is not None
        ]
        pre_avg_balance = sum(pre_balances) / len(pre_balances) if pre_balances else None

        # 信号 #3: 之前 window_days 内的"月均收入"
        pre_income_by_month: Dict[str, float] = {}
        for _, pt in pre_txns:
            if pt.get("direction") != "in":
                continue
            mo = (pt.get("date") or "")[:7]
            if not mo:
                continue
            pre_income_by_month[mo] = pre_income_by_month.get(mo, 0.0) + float(pt.get("amount") or 0)
        pre_avg_income = (
            sum(pre_income_by_month.values()) / len(pre_income_by_month)
            if pre_income_by_month else None
        )

        # 信号 #4: 距申请日 ≤ recent_days(只在"近期窗口"内才标记)
        days_to_apply = (apply_date - tx_date).days
        if days_to_apply > recent_days:
            continue

        # 满足条件才标
        reasons = []
        severity = "warn"

        if pre_avg_balance is not None and pre_avg_balance > 0:
            ratio = amount / pre_avg_balance
            if ratio >= RATIO_TO_PRE_BALANCE_BLOCK:
                severity = "hard_block"
                reasons.append(
                    f"单笔 {amount:,.0f} 是之前 {window_days} 天平均余额 {pre_avg_balance:,.0f} 的 {ratio:.1f} 倍"
                )
            elif ratio >= RATIO_TO_PRE_BALANCE_HIGH:
                severity = max(severity, "high", key=_sev_rank)
                reasons.append(
                    f"单笔 {amount:,.0f} 是之前 {window_days} 天平均余额 {pre_avg_balance:,.0f} 的 {ratio:.1f} 倍"
                )

        if pre_avg_income is not None and pre_avg_income > 0:
            income_ratio = amount / pre_avg_income
            if income_ratio >= (1.0 / RATIO_TO_PRE_INCOME_WARN):  # pre_income < amount * 0.3
                reasons.append(
                    f"之前 {window_days} 天月均收入 {pre_avg_income:,.0f},本笔 {amount:,.0f} 远超正常收入"
                )

        if not reasons:
            continue

        sudden_list.append(SuddenInflow(
            txn_idx=orig_idx,
            date=t["date"],
            amount=amount,
            description=t.get("description"),
            page=t.get("page"),
            pre_avg_balance_90d=round(pre_avg_balance, 2) if pre_avg_balance is not None else None,
            pre_avg_income_90d=round(pre_avg_income, 2) if pre_avg_income is not None else None,
            severity=severity,
            reason="; ".join(reasons),
        ))

    return sudden_list


def _to_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return date(1900, 1, 1)


def _sev_rank(s: str) -> int:
    """给 severity 排序用,warn < high < hard_block"""
    return {"warn": 0, "high": 1, "hard_block": 2}.get(s, 0)


# ---------------------------------------------------------------- #
# 与 balance_chain_check 集成                                          #
# ---------------------------------------------------------------- #
def merge_sudden_into_financial_report(report, sudden_list: List[SuddenInflow]) -> None:
    """把 sudden_inflows 合并进 FinancialReviewReport。

    就地修改 report.sudden_inflows + findings + verdict。
    """
    report.sudden_inflows = [
        {
            "txn_idx": s.txn_idx,
            "date": s.date,
            "amount": s.amount,
            "description": s.description,
            "page": s.page,
            "severity": s.severity,
            "reason": s.reason,
        }
        for s in sudden_list
    ]

    # Findings 给 diagnoser
    if not sudden_list:
        return
    # 取最严重的
    top = max(sudden_list, key=lambda s: _sev_rank(s.severity))
    if top.severity == "hard_block":
        report.verdict = "block"
    elif top.severity == "high" and report.verdict != "block":
        report.verdict = "block"
    elif report.verdict == "pass":
        report.verdict = "warn"