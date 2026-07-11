"""余额链连续性检查 (W53 财务审核)

为什么这个检查最值钱
--------------------
签证官/银行流水造假最常见的两个破绽:
  1. 缺页(把"高消费的那页"截掉)
  2. PS 改数字(把余额改大、把工资改多)

两种破绽都能用同一条数学规则抓到:
    prev.balance + tx.direction_amount == curr.balance
(允许小浮点误差)

策略 (A 方案,跟产品确认):
- 如果某条 transaction 没有 balance 字段 -> 跳过,不报 critical,只 info 提示
  用户上传的"中国手机银行截图"很多不带余额列,做不了余额链不算 bug。
- 如果只有少量 transaction 有 balance (<30%) -> 标记 confidence=low,判定 Unknown
- 如果连续 5+ 笔有 balance 但断链 -> critical,定位具体哪几笔
- 单笔断链可能是 OCR 误差 -> warn (但仍报,让用户复核)

返回结构
--------
FinancialReviewReport 含:
    balance_chain_ok: True/False/None
        True  - 全部对得上
        False - 有断链
        None  - 数据不足以判断(>=30% 缺 balance 字段)
    balance_chain_breaks: [{idx, prev_date, curr_date, prev_balance, expected_balance, actual_balance, diff}]
    balance_chain_coverage: 0.0..1.0   (有 balance 字段的 txn 占比)
    findings: [Finding]                 # 报告里给 diagnoser 用
    verdict: "pass"|"warn"|"block"|"unknown"

Finding 带 page 索引,前端可以指回原页。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# 阈值                                                                #
# ---------------------------------------------------------------- #
# 浮点容差:银行四舍五入 + OCR 误差,1 分钱级别
_BALANCE_TOLERANCE = 0.02
# 余额字段覆盖率门槛:低于这个判 Unknown,不做余额链判断
_BALANCE_COVERAGE_MIN = 0.3
# 连续断链 N 笔以上 -> critical (block verdict),否则 warn
_CRITICAL_BREAK_THRESHOLD = 5


# ---------------------------------------------------------------- #
# 数据结构                                                            #
# ---------------------------------------------------------------- #
@dataclass
class BalanceChainBreak:
    """一笔断链。"""
    idx: int                       # transactions[] 里的索引
    prev_date: Optional[str]
    curr_date: Optional[str]
    prev_balance: float            # 上一笔交易后余额
    expected_balance: float        # 按公式算出的期望值
    actual_balance: float          # 实际 OCR 到的下一笔余额
    diff: float                    # actual - expected
    description: Optional[str] = None
    page: Optional[int] = None     # 指回原页(给前端定位)


@dataclass
class Finding:
    """一条审核意见。给 visa_diagnoser 用。"""
    code: str                      # bank.balance_chain_break 等
    severity: str                  # critical|warn|info
    title: str
    detail: str
    evidence: Optional[Dict[str, Any]] = None  # {page, bbox, txn_idx}
    fix_suggestion: Optional[str] = None


@dataclass
class FinancialReviewReport:
    """一份银行流水的审核报告 (W53)。"""
    material_group_id: str = ""
    source_country: str = ""
    destination: str = ""
    currency: str = ""
    page_count: int = 0
    coverage_months: int = 0
    txn_count: int = 0

    # 余额链 (W53 P0)
    balance_chain_ok: Optional[bool] = None    # True=通 False=断 None=无法判断
    balance_chain_breaks: List[BalanceChainBreak] = field(default_factory=list)
    balance_chain_coverage: float = 0.0       # 有 balance 字段的 txn 占比

    # 占位 — 后续 W54/W55 填
    missing_months: List[str] = field(default_factory=list)
    ending_balance: Optional[float] = None
    ending_balance_in_dest_ccy: Optional[float] = None
    sudden_inflows: List[Dict[str, Any]] = field(default_factory=list)

    findings: List[Finding] = field(default_factory=list)
    verdict: str = "unknown"                  # pass|warn|block|unknown


# ---------------------------------------------------------------- #
# 主检查                                                              #
# ---------------------------------------------------------------- #
def check_balance_chain(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """对一组 transactions 做余额链连续性检查。

    Args:
        transactions: [{date, amount, balance, direction, page?}, ...]
                      balance 字段可能为 None(无余额列)
                      direction: "in"|"out"
                      amount 永远是正数(方向靠 direction 表达)

    Returns:
        {
            "ok": True/False/None,
            "coverage": 0.0..1.0,    # balance 字段覆盖率
            "breaks": [BalanceChainBreak, ...],
            "verdict": "pass"|"warn"|"block"|"unknown",
            "findings": [Finding, ...],
        }
    """
    if not transactions:
        return {
            "ok": None,
            "coverage": 0.0,
            "breaks": [],
            "verdict": "unknown",
            "findings": [_finding_no_data()],
        }

    # 1) 过滤掉没 balance 的;算覆盖率
    with_balance = [(i, t) for i, t in enumerate(transactions) if t.get("balance") is not None]
    coverage = len(with_balance) / len(transactions)

    if coverage < _BALANCE_COVERAGE_MIN:
        # 数据不足以判断 — 不报 critical,只 info
        return {
            "ok": None,
            "coverage": round(coverage, 3),
            "breaks": [],
            "verdict": "unknown",
            "findings": [_finding_low_coverage(coverage, len(with_balance), len(transactions))],
        }

    # 2) 按日期排序(同日期保留原始顺序 — 同日多笔时余额取最后一笔)
    indexed = list(with_balance)
    indexed.sort(key=lambda x: (x[1].get("date") or "", x[0]))

    breaks: List[BalanceChainBreak] = []
    for j in range(1, len(indexed)):
        prev_idx, prev = indexed[j - 1]
        curr_idx, curr = indexed[j]
        prev_bal = float(prev["balance"])
        curr_bal = float(curr["balance"])
        direction = curr.get("direction")
        amount = float(curr.get("amount") or 0)

        # 期望值: 上一笔余额 + (in 则 +, out 则 -) 当前金额
        if direction == "in":
            expected = prev_bal + amount
        elif direction == "out":
            expected = prev_bal - amount
        else:
            # direction 未知,跳这一笔(算"无法判断")
            continue

        diff = curr_bal - expected
        if abs(diff) > _BALANCE_TOLERANCE:
            breaks.append(BalanceChainBreak(
                idx=curr_idx,
                prev_date=prev.get("date"),
                curr_date=curr.get("date"),
                prev_balance=round(prev_bal, 2),
                expected_balance=round(expected, 2),
                actual_balance=round(curr_bal, 2),
                diff=round(diff, 2),
                description=curr.get("description"),
                page=curr.get("page"),
            ))

    # 3) 判定 verdict
    if not breaks:
        return {
            "ok": True,
            "coverage": round(coverage, 3),
            "breaks": [],
            "verdict": "pass",
            "findings": [],
        }

    if len(breaks) >= _CRITICAL_BREAK_THRESHOLD:
        verdict = "block"
        severity = "critical"
    else:
        verdict = "warn"
        severity = "warn"

    findings = [_finding_chain_breaks(breaks, severity=severity)]

    return {
        "ok": False,
        "coverage": round(coverage, 3),
        "breaks": breaks,
        "verdict": verdict,
        "findings": findings,
    }


def build_financial_report(
    transactions: List[Dict[str, Any]],
    *,
    material_group_id: str = "",
    source_country: str = "",
    destination: str = "",
    currency: str = "",
    page_count: int = 0,
    coverage_months: int = 0,
    ending_balance: Optional[float] = None,
) -> FinancialReviewReport:
    """构造 FinancialReviewReport,跑余额链检查并填字段。

    Args:
        transactions: parser 出的 transactions[]
        其他字段由 caller 提供。
    """
    chain = check_balance_chain(transactions)

    report = FinancialReviewReport(
        material_group_id=material_group_id,
        source_country=source_country,
        destination=destination,
        currency=currency,
        page_count=page_count,
        coverage_months=coverage_months,
        txn_count=len(transactions),
        balance_chain_ok=chain["ok"],
        balance_chain_breaks=chain["breaks"],
        balance_chain_coverage=chain["coverage"],
        ending_balance=ending_balance,
        findings=chain["findings"],
        verdict=chain["verdict"],
    )
    return report


# ---------------------------------------------------------------- #
# Findings (诊断意见生成)                                              #
# ---------------------------------------------------------------- #
def _finding_no_data() -> Finding:
    return Finding(
        code="bank.balance_chain_no_data",
        severity="info",
        title="未提供交易明细,无法做余额链审核",
        detail="这条材料没有可用的交易记录,余额链连续性检查无法执行。请上传清晰可读的银行流水 PDF/截图。",
        fix_suggestion="请上传包含交易明细的银行流水(最好含余额列)。",
    )


def _finding_low_coverage(coverage: float, with_b: int, total: int) -> Finding:
    return Finding(
        code="bank.balance_chain_low_coverage",
        severity="info",
        title=f"仅 {with_b}/{total} 条交易含余额字段",
        detail=f"余额字段覆盖率 {coverage:.0%},低于 {_BALANCE_COVERAGE_MIN:.0%} 门槛,余额链连续性检查无法可靠执行(可能是手机银行截图无余额列)。",
        fix_suggestion="建议上传含余额列的银行流水(PDF/网银 PC 版),以便做更严的真实性审核。",
        evidence={"coverage": coverage, "with_balance": with_b, "total": total},
    )


def _finding_chain_breaks(breaks: List[BalanceChainBreak], *, severity: str) -> Finding:
    """余额链断链 — 严重可能是缺页或篡改。"""
    sample = breaks[0]
    if severity == "critical":
        title = f"余额链严重不连续({len(breaks)} 处断链)"
        detail = (
            f"检测到 {len(breaks)} 处余额断链,例如 {sample.prev_date} → {sample.curr_date}:"
            f"上一笔余额 {sample.prev_balance:,.2f},本笔 {sample.curr_date} 期望 {sample.expected_balance:,.2f},"
            f"实际 {sample.actual_balance:,.2f}(差 {sample.diff:+,.2f})。"
            f"这种情况可能是缺页(漏掉中间几笔)或余额数字被修改。"
        )
        fix = "请核对原始流水,确认是否有页缺失或余额数字被人为修改。"
    else:
        title = f"余额链存在 {len(breaks)} 处小幅不一致"
        detail = (
            f"检测到 {len(breaks)} 处余额小幅不一致(容差 ¥{_BALANCE_TOLERANCE})。"
            f"例: {sample.prev_date} → {sample.curr_date} 差 {sample.diff:+,.2f}。"
            f"可能为 OCR 误读,建议复核。"
        )
        fix = "请核对 OCR 识别是否正确,特别是余额数字。"

    evidence = {
        "break_count": len(breaks),
        "sample": {
            "prev_date": sample.prev_date,
            "curr_date": sample.curr_date,
            "diff": sample.diff,
            "page": sample.page,
        },
        "pages": sorted({b.page for b in breaks if b.page is not None}),
    }
    return Finding(
        code="bank.balance_chain_break",
        severity=severity,
        title=title,
        detail=detail,
        fix_suggestion=fix,
        evidence=evidence,
    )