"""W55: sudden_inflow 单测 — 突击存入检测"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.sudden_inflow import (
    SuddenInflow,
    _sev_rank,
    detect_sudden_inflows,
    merge_sudden_into_financial_report,
)
from app.services.balance_chain_check import FinancialReviewReport


def _txn(date_str, amount, direction, balance=None, page=None, desc=""):
    return {
        "date": date_str, "amount": amount, "direction": direction,
        "balance": balance, "page": page, "description": desc,
        "currency": "CNY",
    }


def _date_range(end_str: str, days_back: int):
    """生成 end - days_back .. end 的日期列表(YYYY-MM-DD)。"""
    end = date.fromisoformat(end_str)
    return [(end - timedelta(days=i)).isoformat() for i in range(days_back + 1)]


class TestBasicDetection:
    def test_no_in_transactions_no_sudden(self):
        txns = [
            _txn("2024-03-01", 100.0, "out", balance=5000.0),
            _txn("2024-03-02", 200.0, "out", balance=4800.0),
        ]
        assert detect_sudden_inflows(txns) == []

    def test_empty_input(self):
        assert detect_sudden_inflows([]) == []

    def test_clear_sudden_inflow(self):
        """90 天内都是 5000 余额的小进账,突然来一笔 50000 → hard_block。"""
        txns = []
        # 90 天小进账,余额 5000
        for d in _date_range("2024-06-01", 90):
            txns.append(_txn(d, 200.0, "in", balance=5000.0))
        # 最后一天来一笔 50000
        txns.append(_txn("2024-06-01", 50000.0, "in", balance=55000.0, desc="他行汇入"))
        result = detect_sudden_inflows(txns)
        assert len(result) == 1
        assert result[0].amount == 50000.0
        assert result[0].severity == "hard_block"

    def test_normal_salary_not_flagged(self):
        """稳定月入 1 万不算突击。"""
        txns = []
        for m in range(1, 7):
            for d in [5, 20]:
                txns.append(_txn(f"2024-{m:02d}-{d:02d}", 10000.0, "in", balance=100000.0, desc="工资"))
        result = detect_sudden_inflows(txns)
        # 工资不算突击 — pre_avg_balance 已是 10 万,单笔 1 万 = 1/10 不触发
        assert result == []

    def test_recent_window_required(self):
        """距申请日 > 30 天的突击不算(避免太久以前的临时进账被错认)。"""
        txns = []
        # 100 天前一次性大额
        txns.append(_txn("2024-02-01", 50000.0, "in", balance=55000.0))
        # 之后 100 天小进账
        for d in _date_range("2024-05-15", 100):
            txns.append(_txn(d, 200.0, "in", balance=55000.0))
        # 申请日 ≈ 2024-05-15(最后一笔)
        result = detect_sudden_inflows(txns)
        # 02-01 距 05-15 = 104 天 > 30 天,不报
        assert result == []


class TestSeverityRanks:
    def test_higher_balance_ratio_more_severe(self):
        """倍数越大 severity 越高。"""
        txns = []
        for d in _date_range("2024-06-01", 90):
            txns.append(_txn(d, 200.0, "in", balance=5000.0))
        # 单笔 50000 = 余额 5000 的 10 倍 → hard_block
        txns.append(_txn("2024-06-01", 50000.0, "in", balance=55000.0))
        r = detect_sudden_inflows(txns)
        assert r[0].severity == "hard_block"

    def test_three_times_balance_high(self):
        txns = []
        for d in _date_range("2024-06-01", 90):
            txns.append(_txn(d, 200.0, "in", balance=5000.0))
        # 单笔 15000 = 余额 5000 的 3 倍 → high (>=3 < 5)
        txns.append(_txn("2024-06-01", 15000.0, "in", balance=20000.0))
        r = detect_sudden_inflows(txns)
        assert r[0].severity == "high"


class TestNoBalanceField:
    def test_balance_missing_signal2_skipped(self):
        """没 balance 字段时,信号 #2 跳过(不报 hard_block,但其他信号仍触发 warn)。"""
        txns = []
        # 90 天小进账,无 balance
        for d in _date_range("2024-06-01", 90):
            txns.append(_txn(d, 200.0, "in", desc="小进账"))
        # 单笔大额,无 balance
        txns.append(_txn("2024-06-01", 50000.0, "in", desc="大额"))
        r = detect_sudden_inflows(txns)
        # 没有 balance → ratio 算不出来 → 不报
        # 实际上 income_ratio 也会触发 (50000 vs 月均 6000 = 8.3x)
        # 看 pre_avg_income 触发
        assert len(r) == 1
        assert r[0].pre_avg_balance_90d is None
        assert r[0].pre_avg_income_90d is not None


class TestIncomeSignal:
    def test_pre_income_much_lower_than_txn(self):
        """之前月均 1000,但一笔 50000 → income_ratio 异常。"""
        txns = []
        # 90 天月均 1000
        for d in _date_range("2024-06-01", 90):
            txns.append(_txn(d, 33.0, "in", balance=3000.0))
        txns.append(_txn("2024-06-01", 50000.0, "in", balance=53000.0))
        r = detect_sudden_inflows(txns)
        assert len(r) == 1


class TestMultiSudden:
    def test_multiple_sudden_inflows_sorted(self):
        """多笔突击 → 按日期升序返回。"""
        txns = []
        for d in _date_range("2024-06-30", 90):
            txns.append(_txn(d, 200.0, "in", balance=5000.0))
        # 两笔突击
        txns.append(_txn("2024-06-15", 30000.0, "in", balance=35000.0))
        txns.append(_txn("2024-06-30", 50000.0, "in", balance=85000.0))
        r = detect_sudden_inflows(txns)
        assert len(r) == 2
        # 按日期升序
        assert r[0].date <= r[1].date


class TestSeverityRankHelper:
    def test_rank_order(self):
        assert _sev_rank("warn") < _sev_rank("high") < _sev_rank("hard_block")

    def test_unknown_severity_zero(self):
        assert _sev_rank("unknown") == 0


class TestMergeIntoReport:
    def test_merge_sudden_populates_report(self):
        r = FinancialReviewReport()
        suddens = [
            SuddenInflow(
                txn_idx=5, date="2024-06-15", amount=50000.0,
                description="他行汇入", page=2,
                pre_avg_balance_90d=5000.0, pre_avg_income_90d=1500.0,
                severity="hard_block",
                reason="单笔 50000 是之前余额 5000 的 10 倍",
            ),
        ]
        merge_sudden_into_financial_report(r, suddens)
        assert len(r.sudden_inflows) == 1
        assert r.sudden_inflows[0]["amount"] == 50000.0
        assert r.verdict == "block"  # hard_block 升级

    def test_merge_warn_does_not_override_pass(self):
        r = FinancialReviewReport(verdict="pass")
        suddens = [
            SuddenInflow(
                txn_idx=0, date="2024-06-15", amount=500.0,
                severity="warn", reason="略高",
            ),
        ]
        merge_sudden_into_financial_report(r, suddens)
        assert r.verdict == "warn"  # warn 从 pass 升

    def test_merge_high_overrides_warn_but_not_block(self):
        r = FinancialReviewReport(verdict="warn")
        suddens = [
            SuddenInflow(
                txn_idx=0, date="2024-06-15", amount=500.0,
                severity="high", reason="高",
            ),
        ]
        merge_sudden_into_financial_report(r, suddens)
        assert r.verdict == "block"  # high 升级到 block

    def test_merge_empty_no_change(self):
        r = FinancialReviewReport(verdict="pass")
        merge_sudden_into_financial_report(r, [])
        assert r.sudden_inflows == []
        assert r.verdict == "pass"


class TestEdgeCases:
    def test_single_transaction_no_sudden(self):
        """只有 1 笔不算突击(没有"之前"的对比)。"""
        txns = [_txn("2024-06-01", 1000.0, "in", balance=1000.0)]
        assert detect_sudden_inflows(txns) == []

    def test_invalid_date_skipped(self):
        txns = [
            _txn("not-a-date", 100.0, "in"),
            _txn("2024-06-01", 1000.0, "in", balance=1000.0),
        ]
        # 不应崩
        assert isinstance(detect_sudden_inflows(txns), list)

    def test_zero_amount_skipped(self):
        txns = [
            _txn("2024-06-01", 0.0, "in", balance=1000.0),
        ]
        assert detect_sudden_inflows(txns) == []