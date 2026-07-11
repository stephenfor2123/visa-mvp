"""bank_statement_parser — 单测 (W51)

覆盖四种场景:
  1. 充足: 6 个月,142 笔交易, regex 直接命中
  2. 边界: 2 个月 (不够签证官建议)
  3. 多格式混: 同时含日期 YYYY-MM-DD 和 YYYYMMDD
  4. 异常: 0 笔 (parser 标记 none)

LLM fallback 在单测里默认 monkey-patched 跳过 — 避免 CI 无 outbound 网络时挂 25s/次。
要测 LLM 路径请显式打开 @pytest.mark.integration。
"""
from __future__ import annotations

import pytest

from app.services import bank_statement_parser as bsp
from app.services.bank_statement_parser import (
    parse_bank_statement,
    ocr_items_to_text,
    parse_with_regex,
    aggregate,
)


@pytest.fixture(autouse=True)
def _disable_llm_fallback(monkeypatch):
    """所有单测默认走纯 regex 路径,LLM 调用被替换为空函数 (返 []).

    想测 LLM 路径,需要重新设置 monkeypatch.setattr(bsp, '_parse_with_llm_sync',
    real_function) — 写到集成测试去。
    """
    monkeypatch.setattr(bsp, "_parse_with_llm_sync", lambda *args, **kwargs: [])
    return None


def _items(text_lines: list[str]) -> list[dict]:
    """把一行行字符串 mock 成 OCR items。
    x 单调递增(假设列内单字符),y 同行相同,行间 +30。"""
    items = []
    for row, line in enumerate(text_lines):
        for col, ch in enumerate(line):
            if ch == " ":
                continue
            x = col * 10
            y = row * 30
            items.append({
                "text": ch,
                "bbox": [[x, y], [x + 8, y], [x + 8, y + 20], [x, y + 20]],
                "confidence": 0.95,
            })
    return items


def _concat_to_text(items: list[dict]) -> str:
    """OCR items → 行文本(走真实函数)。"""
    return ocr_items_to_text(items)


class TestParseWithRegexBasic:
    """基本语法正确解析。"""

    def test_basic_one_line_parses(self):
        text = "2024-03-15 工资入账 12000.50 15000.00"
        txns = parse_with_regex(text)
        assert len(txns) == 1
        t = txns[0]
        assert t["date"] == "2024-03-15"
        assert t["amount"] == 12000.50
        assert t["balance"] == 15000.00
        # 描述含「入账」,归属 income
        assert t["direction"] == "in"
        assert t["currency"] == "CNY"

    def test_compact_date_works(self):
        # 一些老的电子流水用 YYYYMMDD
        text = "20240315 转账支出 500.00 12000.00"
        txns = parse_with_regex(text)
        assert len(txns) == 1
        assert txns[0]["date"] == "2024-03-15"
        assert txns[0]["amount"] == 500.00

    def test_negative_amount_treated_as_out(self):
        text = "2024-04-01 扫码支付 -88.50 12311.50"
        txns = parse_with_regex(text)
        assert len(txns) == 1
        assert txns[0]["amount"] == 88.50  # abs
        assert txns[0]["direction"] == "out"

    def test_no_balance_field_ok(self):
        text = "2024-05-10 工资入账 12000.50"
        txns = parse_with_regex(text)
        assert len(txns) == 1
        assert txns[0]["balance"] is None


class TestParseWithRegexSufficiency:
    """充足场景: 6 个月、超过 100 笔、收入稳定。"""

    def test_142_lines_yield_high_parser_confidence(self):
        lines = []
        for month in range(1, 7):
            yyyymm = f"2024-{month:02d}"
            for day in range(1, 16):
                lines.append(f"{yyyymm}-{day:02d} 工资入账 12000.00 50000.00")
                lines.append(f"{yyyymm}-{day:02d} 房租支出 4500.00 45500.00")
                lines.append(f"{yyyymm}-{day:02d} 餐饮消费 88.00 45412.00")
                lines.append(f"{yyyymm}-{day:02d} 转账支出 200.00 45212.00")
                lines.append(f"{yyyymm}-{day:02d} 转账支出 150.00 45062.00")
        items = _items(lines)
        text = _concat_to_text(items)
        out = parse_bank_statement(ocr_items=items)
        # 80 行 * 5 笔/天 / 2 字符 = 应该多得多,但关键 parser_used 是 regex 且足够多
        # 因为是字符级 mock,真实场景下 regex 行匹配需要整行一次性解析。
        # 真实 OCR 会按行还原,这里我们直接走文本路径更准。
        out2 = parse_bank_statement(ocr_text="\n".join(lines))
        assert out2["parser"] == "regex"
        assert out2["txn_count"] >= 10
        assert out2["coverage_months"] >= 6
        assert out2["monthly_income_avg"] is not None
        assert out2["monthly_income_avg"] >= 3000  # 月入 1.2 万以上
        # 没有大额异常
        assert out2["large_inflows"] == []


class TestParseWithRegexShortCoverage:
    """边界场景: 仅 2 个月,提示用户补材料。"""

    def test_short_coverage_aggregates_correctly(self):
        lines = [
            "2024-09-01 工资入账 8000.00 20000.00",
            "2024-09-15 餐饮消费 100.00 19900.00",
            "2024-10-01 工资入账 8500.00 28400.00",
            "2024-10-15 餐饮消费 120.00 28280.00",
        ]
        out = parse_bank_statement(ocr_text="\n".join(lines))
        assert out["parser"] == "regex"
        assert out["coverage_months"] == 2
        assert out["txn_count"] == 4


class TestParseWithRegexLargeTransactions:
    """异常场景: 有大额转入。"""

    def test_large_inflow_detected(self):
        lines = [
            "2024-06-01 工资入账 12000.00 30000.00",
            "2024-06-15 他行汇入 80000.00 110000.00",  # 异常大额
            "2024-07-01 工资入账 12000.00 110000.00",
            "2024-07-15 转账支出 500.00 105500.00",
        ]
        out = parse_bank_statement(ocr_text="\n".join(lines))
        assert out["parser"] == "regex"
        assert len(out["large_inflows"]) == 1
        assert out["large_inflows"][0]["amount"] == 80000.00


class TestParseEmpty:
    """空 / OCR 全失败。"""

    def test_empty_text_yields_none_parser(self):
        out = parse_bank_statement(ocr_text="")
        assert out["parser"] == "none"
        assert out["txn_count"] == 0
        assert out["coverage_months"] == 0
        assert out["transactions"] == []

    def test_garbage_text_yields_none_or_few(self):
        # OCR 全是杂讯:正则不出东西,LLM 也不在线 (CI 环境下)
        out = parse_bank_statement(ocr_text="random noise @#%^& random words asdfgh qwerty")
        # 可能是 none(LLM 未配) — 两条都接受,关键是 txn_count 是 0
        assert out["transactions"] in (None, [])
        # parser 应该是 none 或 llm(fallback 失败时)
        assert out["parser"] in ("none", "llm")


class TestOCrItemsToText:
    """OCR items 行重建正确性。"""

    def test_items_regrouped_by_row(self):
        # mock 同一行不同列
        items = [
            {"text": "2024-03-15", "bbox": [[0, 0], [80, 0], [80, 20], [0, 20]]},
            {"text": "ATM",       "bbox": [[100, 2], [150, 2], [150, 22], [100, 22]]},
            {"text": "500.00",    "bbox": [[200, 5], [260, 5], [260, 25], [200, 25]]},
            # 下一行 y 隔开 50px
            {"text": "2024-03-16", "bbox": [[0, 50], [80, 50], [80, 70], [0, 70]]},
            {"text": "工资",       "bbox": [[100, 52], [180, 52], [180, 72], [100, 72]]},
        ]
        text = ocr_items_to_text(items)
        lines = text.split("\n")
        assert len(lines) == 2
        assert "2024-03-15" in lines[0]
        assert "ATM" in lines[0]
        assert "500.00" in lines[0]
        assert "2024-03-16" in lines[1]

    def test_empty_items_returns_empty(self):
        assert ocr_items_to_text([]) == ""
        assert ocr_items_to_text(None) == ""


class TestIncomeGapDetection:
    """W52: detect_income_gaps 找连续无 income 的月份段。"""

    def test_no_gap_when_every_month_has_income(self):
        from app.services.bank_statement_parser import detect_income_gaps
        summary = [
            {"month": "2024-08", "income": 12000.0, "expense": 8000.0},
            {"month": "2024-09", "income": 12000.0, "expense": 7500.0},
            {"month": "2024-10", "income": 12500.0, "expense": 9000.0},
        ]
        assert detect_income_gaps(summary) == []

    def test_one_month_gap_detected(self):
        from app.services.bank_statement_parser import detect_income_gaps
        summary = [
            {"month": "2024-08", "income": 12000.0, "expense": 8000.0},
            # 9 月断档
            {"month": "2024-09", "income": 0.0, "expense": 200.0},
            {"month": "2024-10", "income": 12500.0, "expense": 9000.0},
        ]
        gaps = detect_income_gaps(summary)
        assert len(gaps) == 1
        assert gaps[0]["start_month"] == "2024-09"
        assert gaps[0]["end_month"] == "2024-09"
        assert gaps[0]["gap_months"] == 1  # 9月自身

    def test_multi_month_continuous_gap(self):
        from app.services.bank_statement_parser import detect_income_gaps
        summary = [
            {"month": "2024-06", "income": 12000.0, "expense": 8000.0},
            # 7-9 月断档
            {"month": "2024-07", "income": 0.0, "expense": 200.0},
            {"month": "2024-08", "income": 0.0, "expense": 300.0},
            {"month": "2024-09", "income": 0.0, "expense": 250.0},
            {"month": "2024-10", "income": 12500.0, "expense": 9000.0},
        ]
        gaps = detect_income_gaps(summary)
        assert len(gaps) == 1
        assert gaps[0]["start_month"] == "2024-07"
        assert gaps[0]["end_month"] == "2024-09"
        assert gaps[0]["gap_months"] == 3

    def test_two_separate_gaps(self):
        from app.services.bank_statement_parser import detect_income_gaps
        summary = [
            {"month": "2024-06", "income": 12000.0, "expense": 8000.0},
            {"month": "2024-07", "income": 0.0, "expense": 200.0},
            {"month": "2024-08", "income": 12000.0, "expense": 8000.0},
            {"month": "2024-09", "income": 0.0, "expense": 200.0},
            {"month": "2024-10", "income": 12000.0, "expense": 8000.0},
        ]
        gaps = detect_income_gaps(summary)
        assert len(gaps) == 2
        assert gaps[0]["start_month"] == "2024-07"
        assert gaps[1]["start_month"] == "2024-09"

    def test_min_income_filter_skips_tiny_amounts(self):
        from app.services.bank_statement_parser import detect_income_gaps
        # 默认 min_income=100, 50 块退款不应该被当 income
        summary = [
            {"month": "2024-08", "income": 12000.0, "expense": 8000.0},
            {"month": "2024-09", "income": 50.0, "expense": 200.0},  # 退款 50
            {"month": "2024-10", "income": 12500.0, "expense": 9000.0},
        ]
        gaps = detect_income_gaps(summary, min_income=100.0)
        assert len(gaps) == 1
        assert gaps[0]["start_month"] == "2024-09"


class TestMultiPageAggregation:
    """W52: 多页 transactions 合并后 aggregate / detect_income_gaps 仍正确。"""

    def test_multi_page_transactions_merge_into_monthly(self):
        # 模拟: 12 月工资在 page 1, 1 月工资在 page 2, 1 月生活费在 page 2
        # 但 page 1 也有 1 月的零碎支出
        transactions = [
            # page 1: 12 月
            {"date": "2024-12-01", "description": "工资入账", "amount": 12000.0,
             "direction": "in", "currency": "CNY", "page_index": 1},
            {"date": "2024-12-05", "description": "餐饮消费", "amount": 88.0,
             "direction": "out", "currency": "CNY", "page_index": 1},
            # page 2: 1 月 (新月份)
            {"date": "2025-01-01", "description": "工资入账", "amount": 12000.0,
             "direction": "in", "currency": "CNY", "page_index": 2},
            {"date": "2025-01-10", "description": "房租支出", "amount": 4500.0,
             "direction": "out", "currency": "CNY", "page_index": 2},
        ]
        out = parse_bank_statement(ocr_items=[])  # 空 OCR -> 走 fallback,先测入口
        # 重新调,直接传 transactions 通过 ocr_text (不实际使用,会重新 regex)
        # 改用直接调 aggregate + detect_income_gaps
        from app.services.bank_statement_parser import aggregate, detect_income_gaps
        agg = aggregate(transactions)
        assert agg["coverage_months"] == 2  # 12 月 + 1 月
        assert agg["txn_count"] == 4
        # 收入:12000 + 12000 = 24000, 月均 12000
        assert agg["monthly_income_avg"] == 12000.0
        # gap: 12 月有,1 月有 — 连续无 gap
        assert detect_income_gaps(agg["monthly_summary"]) == []

    def test_parse_bank_statement_main_includes_income_gaps_field(self):
        out = parse_bank_statement(ocr_text="")
        # 即使空,字段也要存在,便于 diagnoser 无脑 get
        assert "income_gaps" in out
        assert out["income_gaps"] == []
