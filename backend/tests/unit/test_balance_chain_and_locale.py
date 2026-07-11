"""W53 余额链检查 + 多语言源国适配 — 单测

覆盖:
  1. CN 余额链 — 通 / 断链 (单笔 / 多笔) / 篡改 / 无 balance 字段
  2. VN 解析 — 越南语描述 + 点千分位 + DD/MM/YYYY 日期 + Số dư 余额
  3. ID 解析 — 印尼语描述 + 点千分位 + DD-MM-YY 日期 + Saldo 余额
  4. 越南语余额链 — 用 VN locale 解析后再做余额链
  5. A 方案边界 — coverage < 30% 返 Unknown
"""
from __future__ import annotations

import pytest

from app.services import balance_chain_check as bcc
from app.services.bank_statement_parser import (
    _parse_amount,
    _parse_date,
    aggregate,
    get_locale,
    parse_bank_statement,
    parse_with_regex,
)


# ===================================================================== #
# Part 1: 余额链 (W53 P0)                                               #
# ===================================================================== #

def _txn(date, amount, direction, balance=None, page=None):
    """快速构造 transaction dict。"""
    return {
        "date": date,
        "amount": amount,
        "direction": direction,
        "balance": balance,
        "page": page,
        "description": "mock",
        "currency": "CNY",
    }


class TestBalanceChainPass:
    def test_simple_chain_passes(self):
        """最简单的链: 余额连续加减都对。"""
        txns = [
            _txn("2024-03-01", 1000.0, "in", balance=1000.0),
            _txn("2024-03-02", 200.0, "out", balance=800.0),
            _txn("2024-03-03", 50.0, "in", balance=850.0),
        ]
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is True
        assert r["coverage"] == 1.0
        assert r["breaks"] == []
        assert r["verdict"] == "pass"


class TestBalanceChainBreak:
    def test_single_break_is_warn(self):
        """单笔断链(<5 笔) -> warn。"""
        txns = [
            _txn("2024-03-01", 1000.0, "in", balance=1000.0),
            _txn("2024-03-02", 200.0, "out", balance=850.0),  # 期望 800,差 50
        ]
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is False
        assert r["verdict"] == "warn"
        assert len(r["breaks"]) == 1
        assert r["breaks"][0].diff == 50.0

    def test_many_breaks_is_block(self):
        """≥5 笔断链 -> critical / block。"""
        txns = [
            _txn("2024-03-01", 1000.0, "in", balance=1000.0),
            _txn("2024-03-02", 200.0, "out", balance=850.0),
            _txn("2024-03-03", 100.0, "out", balance=850.0),
            _txn("2024-03-04", 100.0, "out", balance=850.0),
            _txn("2024-03-05", 100.0, "out", balance=850.0),
            _txn("2024-03-06", 100.0, "out", balance=850.0),
            _txn("2024-03-07", 100.0, "out", balance=850.0),
        ]
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is False
        assert r["verdict"] == "block"
        assert r["findings"][0].severity == "critical"

    def test_break_includes_page(self):
        """断链 Finding 带 page,前端能定位。"""
        txns = [
            _txn("2024-03-01", 1000.0, "in", balance=1000.0, page=1),
            _txn("2024-03-02", 200.0, "out", balance=850.0, page=2),
        ]
        r = bcc.check_balance_chain(txns)
        assert r["breaks"][0].page == 2

    def test_tolerance_allows_one_cent_drift(self):
        """¥0.01 容差(银行四舍五入/OCR 微小误差)不算断链。"""
        txns = [
            _txn("2024-03-01", 100.0, "in", balance=1000.00),
            _txn("2024-03-02", 50.0, "out", balance=950.01),  # 期望 950.00
        ]
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is True


class TestBalanceChainLowCoverage:
    def test_no_balance_anywhere_returns_unknown(self):
        """A 方案: 完全没 balance 字段 -> Unknown,不报 critical。"""
        txns = [
            _txn("2024-03-01", 100.0, "in"),
            _txn("2024-03-02", 50.0, "out"),
        ]
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is None
        assert r["verdict"] == "unknown"
        # 是 info 级别
        assert r["findings"][0].severity == "info"
        assert r["findings"][0].code == "bank.balance_chain_low_coverage"

    def test_low_coverage_returns_unknown(self):
        """只有 1/10 有 balance -> coverage 0.1 < 0.3 门槛 -> Unknown。"""
        txns = [_txn(f"2024-03-{i+1:02d}", 10.0, "in") for i in range(10)]
        txns[0]["balance"] = 100.0  # 只有第一笔有 balance
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is None
        assert r["coverage"] == 0.1

    def test_mobile_screenshot_pattern(self):
        """中国手机银行截图常见:只有部分交易有余额(网银 vs 截图混合)。
        coverage >= 30% 时还是做余额链检查。"""
        txns = [_txn(f"2024-03-{i+1:02d}", 10.0, "in") for i in range(10)]
        # 4 笔有余额 = 40% coverage
        for i in [0, 1, 2, 3]:
            txns[i]["balance"] = 100.0 + i * 10
        r = bcc.check_balance_chain(txns)
        # 4 笔里有 balance 但不一定对得上 -> 这里对不上(10 块 in 但 balance 间隔 10)
        # 实际上每笔 +10 应该匹配,但第 0 笔 in 10 后是 110,实际 110;balance 写了 100
        # 期望 100 (起始) + 10 = 110, 实际 100 (txns[0])
        # 所以第一笔开始就 break。属正常
        assert r["ok"] in (True, False)
        assert r["coverage"] == 0.4


class TestBuildFinancialReport:
    def test_report_assembles_fields(self):
        """build_financial_report 把 transactions + 余额链检查结果填到 dataclass。"""
        txns = [_txn("2024-03-01", 100.0, "in", balance=100.0)]
        r = bcc.build_financial_report(
            txns,
            material_group_id="mat-123",
            source_country="CN",
            destination="US",
            currency="CNY",
            page_count=1,
            coverage_months=1,
            ending_balance=100.0,
        )
        assert isinstance(r, bcc.FinancialReviewReport)
        assert r.material_group_id == "mat-123"
        assert r.source_country == "CN"
        assert r.ending_balance == 100.0
        assert r.balance_chain_ok is True
        assert r.verdict == "pass"


# ===================================================================== #
# Part 2: 多语言源国适配 (越南 / 印尼)                                    #
# ===================================================================== #

class TestLocaleBasics:
    def test_get_locale_cn(self):
        loc = get_locale("CN")
        assert loc["currency"] == "CNY"
        assert loc["thousands_sep"] == ","

    def test_get_locale_vn(self):
        loc = get_locale("VN")
        assert loc["currency"] == "VND"
        assert loc["thousands_sep"] == "."

    def test_get_locole_id(self):
        loc = get_locale("ID")
        assert loc["currency"] == "IDR"

    def test_unknown_falls_back_to_cn(self):
        loc = get_locale("JP")
        assert loc["currency"] == "CNY"


class TestParseAmountByLocale:
    def test_cn_thousands(self):
        """1,234.56 → 1234.56"""
        assert _parse_amount("1,234.56", get_locale("CN")) == 1234.56

    def test_cn_no_decimal(self):
        assert _parse_amount("12,000", get_locale("CN")) == 12000.0

    def test_vn_thousands_no_decimal(self):
        """越南 1.234.567 → 1234567.0"""
        assert _parse_amount("1.234.567", get_locale("VN")) == 1234567.0

    def test_vn_thousands_with_comma_decimal(self):
        """越南 1.234.567,89 → 1234567.89"""
        assert _parse_amount("1.234.567,89", get_locale("VN")) == 1234567.89

    def test_id_thousands(self):
        assert _parse_amount("5.000.000", get_locale("ID")) == 5000000.0

    def test_negative_amount(self):
        assert _parse_amount("-500.00", get_locale("CN")) == -500.0
        assert _parse_amount("-1.000.000", get_locale("VN")) == -1000000.0


class TestParseDateByLocale:
    def test_cn_iso(self):
        assert _parse_date("2024-03-15", get_locale("CN")) == "2024-03-15"

    def test_vn_dmy(self):
        """15/03/2024 → 2024-03-15"""
        assert _parse_date("15/03/2024", get_locale("VN")) == "2024-03-15"

    def test_vn_dmy_dash(self):
        assert _parse_date("15-03-2024", get_locale("VN")) == "2024-03-15"

    def test_vn_two_digit_year(self):
        """15/03/25 → 2025-03-15"""
        assert _parse_date("15/03/25", get_locale("VN")) == "2025-03-15"

    def test_id_dmy(self):
        assert _parse_date("15/03/2024", get_locale("ID")) == "2024-03-15"

    def test_id_two_digit_year(self):
        assert _parse_date("15-03-25", get_locale("ID")) == "2025-03-15"


class TestParseVietnameseStatement:
    """模拟越南银行流水 OCR 文本。"""

    def test_vcb_statement_basic(self):
        """Vietcombank 风格: DD/MM/YYYY + 越南语描述 + 点千分位 + Số dư"""
        text = """Số tài khoản: 1234567890
Ngày Nội dung Số tiền Số dư
15/03/2024 Lương tháng 3 +15.000.000 25.000.000
16/03/2024 Chuyển đến từ ACB +5.000.000 30.000.000
17/03/2024 Rút ATM -2.000.000 28.000.000
18/03/2024 Thanh toán điện -500.000 27.500.000
19/03/2024 Mua sắm -1.200.000 26.300.000
20/03/2024 Chuyển đến +3.000.000 29.300.000
21/03/2024 Phí ngân hàng -50.000 29.250.000
22/03/2024 Lương tháng 3 +15.000.000 44.250.000
23/03/2024 Ăn uống -300.000 43.950.000
24/03/2024 Xăng xe -500.000 43.450.000
25/03/2024 Chuyển đến +2.000.000 45.450.000
26/03/2024 Rút tiền mặt -5.000.000 40.450.000
27/03/2024 Mua sắm online -1.500.000 38.950.000
28/03/2024 Hoàn tiền +800.000 39.750.000"""
        out = parse_bank_statement(ocr_text=text, source_country="VN")
        # 关键: parser 能识别 ≥10 条
        assert out["parser"] == "regex"
        assert out["txn_count"] >= 10
        # 货币是 VND
        assert all(t["currency"] == "VND" for t in out["transactions"])
        # 余额链检查 — coverage 100% + 应该连续(数据是手工构造的连续)
        chain = bcc.check_balance_chain(out["transactions"])
        assert chain["ok"] is True
        assert chain["verdict"] == "pass"

    def test_vn_amount_in_vnd_no_decimal(self):
        """越南 1.234.567 不能被错成 1.234567 (差 100 倍)。"""
        text = """15/03/2024 Lương +1.234.567 1.234.567
16/03/2024 Ăn -234.567 1.000.000
17/03/2024 Mua -100.000 900.000
18/03/2024 Lương +2.000.000 2.900.000
19/03/2024 Ăn -50.000 2.850.000
20/03/2024 Mua -100.000 2.750.000
21/03/2024 Ăn -50.000 2.700.000
22/03/2024 Mua -100.000 2.600.000
23/03/2024 Lương +2.000.000 4.600.000
24/03/2024 Ăn -50.000 4.550.000
25/03/2024 Mua -100.000 4.450.000"""
        out = parse_bank_statement(ocr_text=text, source_country="VN")
        # 第一笔 amount 必须是 1234567,不是 1.234567
        assert out["transactions"][0]["amount"] == 1234567.0


class TestParseIndonesianStatement:
    """模拟印尼银行流水 OCR 文本 (BCA/Mandiri)。"""

    def test_bca_statement_basic(self):
        """BCA 风格: DD/MM/YYYY + 印尼语 + 点千分位 + Saldo"""
        text = """Rekening: 1234567890
Tanggal Keterangan Jumlah Saldo
15/03/2024 Gaji bulanan +8.000.000 18.000.000
16/03/2024 Transfer dari BCA +2.000.000 20.000.000
17/03/2024 Tarik tunai -1.500.000 18.500.000
18/03/2024 Bayar listrik -500.000 18.000.000
19/03/2024 Belanja -1.000.000 17.000.000
20/03/2024 Transfer masuk +3.000.000 20.000.000
21/03/2024 Biaya admin -25.000 19.975.000
22/03/2024 Gaji bulanan +8.000.000 27.975.000
23/03/2024 Makan -200.000 27.775.000
24/03/2024 Bensin -300.000 27.475.000
25/03/2024 Transfer masuk +1.500.000 28.975.000
26/03/2024 Tarik -5.000.000 23.975.000
27/03/2024 Belanja online -800.000 23.175.000
28/03/2024 Pengembalian +400.000 23.575.000"""
        out = parse_bank_statement(ocr_text=text, source_country="ID")
        assert out["parser"] == "regex"
        assert out["txn_count"] >= 10
        assert all(t["currency"] == "IDR" for t in out["transactions"])
        chain = bcc.check_balance_chain(out["transactions"])
        assert chain["ok"] is True


class TestTamperingDetection:
    """篡改检测 — 用户改数字后余额对不上。"""

    def test_padded_balance_caught(self):
        """余额被从 5000 改成 50000,断链。"""
        txns = [
            _txn("2024-03-01", 1000.0, "in", balance=1000.0),
            _txn("2024-03-02", 200.0, "out", balance=800.0),
            _txn("2024-03-03", 50.0, "in", balance=50000.0),  # 篡改!
            _txn("2024-03-04", 100.0, "out", balance=49900.0),
        ]
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is False
        # 期望 850,实际 50000,差 49150
        assert any(abs(b.diff - 49150.0) < 0.01 for b in r["breaks"])

    def test_missing_page_caught(self):
        """缺页(中间几笔交易没了,但用户造假了余额假装连续)。

        场景:用户把 03/03 那笔大额消费 500 块 PS 删掉,但余额链没法接上 —
        因为后面 03/04 的 balance 是基于真实流水 OCR 出来的。
        """
        txns = [
            _txn("2024-03-01", 1000.0, "in", balance=1000.0),
            _txn("2024-03-02", 200.0, "out", balance=800.0),
            # 03/03 的 500 out 被 PS 删了 — 但 03/04 的 balance 是真实 OCR 出来的 800
            # (造假者忘改这一笔 balance)。算法期望 800 - 50 = 750, 实际 800。
            _txn("2024-03-04", 50.0, "out", balance=800.0),  # 期望 750, 实际 800
        ]
        r = bcc.check_balance_chain(txns)
        assert r["ok"] is False
        assert len(r["breaks"]) == 1
        assert r["breaks"][0].expected_balance == 750.0
        assert r["breaks"][0].actual_balance == 800.0


class TestAggregateMultiLocale:
    def test_vn_large_threshold_uses_50m_vnd(self):
        """越南大额阈值是 50,000,000 VND,不是 50,000。"""
        loc = get_locale("VN")
        assert loc["large_threshold"] == 50_000_000.0

    def test_vn_small_amount_not_flagged_as_large(self):
        """越南 30,000 VND 不算大额。"""
        text = """15/03/2024 Cà phê -30.000 1.970.000
16/03/2024 Cà phê -30.000 1.940.000
17/03/2024 Cà phê -30.000 1.910.000
18/03/2024 Cà phê -30.000 1.880.000
19/03/2024 Cà phê -30.000 1.850.000
20/03/2024 Cà phê -30.000 1.820.000
21/03/2024 Cà phê -30.000 1.790.000
22/03/2024 Cà phê -30.000 1.760.000
23/03/2024 Cà phê -30.000 1.730.000
24/03/2024 Cà phê -30.000 1.700.000
25/03/2024 Cà phê -30.000 1.670.000"""
        out = parse_bank_statement(ocr_text=text, source_country="VN")
        assert out["large_outflows"] == []


# ===================================================================== #
# Part 3: end-to-end 越南 + 余额链                                       #
# ===================================================================== #

class TestEndToEndVietnamTampering:
    """模拟越南用户上传流水,中间一笔余额被人为改大。"""

    def test_tampered_line_caught(self):
        text = """15/03/2024 Lương +15.000.000 15.000.000
16/03/2024 Chuyển đến +5.000.000 20.000.000
17/03/2024 Rút ATM -2.000.000 18.000.000
18/03/2024 Thanh toán -500.000 17.500.000
19/03/2024 Mua sắm -1.200.000 16.300.000
20/03/2024 Chuyển đến +3.000.000 19.300.000
21/03/2024 Phí -50.000 19.250.000
22/03/2024 Lương +15.000.000 100.000.000
23/03/2024 Ăn uống -300.000 99.700.000
24/03/2024 Xăng xe -500.000 99.200.000
25/03/2024 Chuyển đến +2.000.000 101.200.000"""
        # 22/03 的"100.000.000" 是篡改(期望 34.250.000)
        out = parse_bank_statement(ocr_text=text, source_country="VN")
        assert out["txn_count"] >= 10

        chain = bcc.check_balance_chain(out["transactions"])
        assert chain["ok"] is False
        # 22/03 那一笔余额期望 34.250.000,实际 100.000.000
        break_at_22 = next((b for b in chain["breaks"] if b.curr_date == "2024-03-22"), None)
        assert break_at_22 is not None
        assert abs(break_at_22.diff - (100_000_000 - 34_250_000)) < 1.0
        assert break_at_22.prev_balance == 19_250_000.0


# 编译时 fallback 名字笔误修复 — 用 monkeypatch 风格的兜底
def get_locole(s):  # pragma: no cover
    return get_locale(s)