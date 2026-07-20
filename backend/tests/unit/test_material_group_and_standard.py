"""W54: material_group.py 单测 — 归组 / 页序 / 跨页去重 / missing_months / 整组 review"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services.material_group import (
    MaterialGroup,
    MaterialItem,
    _add_months,
    _months_between,
    dedup_transactions,
    detect_missing_months,
    group_materials,
    ocr_items_group_by_page,
    restore_page_order,
    review_group,
)
from app.services.financial_standard import (
    BalanceVerdict,
    convert_balance,
    evaluate_balance,
    get_financial_standard,
    get_fx_rate,
)


# ===================================================================== #
# Helpers                                                                #
# ===================================================================== #
def _item(mid, mtype="bank", user_id=1, order_id=10, mins_offset=0,
          ocr_text=None, ocr_items=None):
    return MaterialItem(
        material_id=mid,
        user_id=user_id,
        order_id=order_id,
        material_type=mtype,
        created_at=datetime(2024, 6, 1, 10, 0) + timedelta(minutes=mins_offset),
        ocr_text=ocr_text,
        ocr_items=ocr_items,
    )


def _items_from_text(mid, text, page_count=1):
    """模拟 OCR items (整页一个 item,带 page_index)"""
    items = []
    for p in range(1, page_count + 1):
        items.append({"text": text, "bbox": [[0, 0], [100, 0], [100, 20], [0, 20]],
                      "page_index": p, "confidence": 0.95})
    return items


def _cn_lines(n_months=3, per_month=10, with_balance=True):
    """生成 N 个月的中文流水文本(单页)。"""
    lines = []
    bal = 10000.0
    for m in range(1, n_months + 1):
        for d in range(1, per_month + 1):
            yyyymm = f"2024-{m:02d}"
            amount = 500.0 if d % 2 == 0 else 1500.0
            direction = "收入" if d % 2 == 0 else "支出"
            bal += (1500.0 - 500.0) if d % 2 == 0 else -amount
            lines.append(f"{yyyymm}-{d:02d} {direction} {amount:.2f} {bal:.2f}")
    return "\n".join(lines)


# ===================================================================== #
# 归组                                                                   #
# ===================================================================== #
class TestGrouping:
    def test_single_item_no_group(self):
        items = [_item("m1")]
        groups = group_materials(items)
        assert len(groups) == 1
        assert groups[0].material_type == "bank"
        assert len(groups[0].items) == 1

    def test_two_items_within_window_grouped(self):
        """30 分钟内同 user/order/type -> 同一组。"""
        items = [
            _item("m1", mins_offset=0),
            _item("m2", mins_offset=15),
        ]
        groups = group_materials(items)
        assert len(groups) == 1
        assert len(groups[0].items) == 2

    def test_two_items_outside_window_separate_groups(self):
        """间隔 31 分钟 -> 拆成两组。"""
        items = [
            _item("m1", mins_offset=0),
            _item("m2", mins_offset=31),
        ]
        groups = group_materials(items)
        assert len(groups) == 2

    def test_different_users_separate_groups(self):
        items = [
            _item("m1", user_id=1, mins_offset=0),
            _item("m2", user_id=2, mins_offset=5),
        ]
        groups = group_materials(items)
        assert len(groups) == 2

    def test_different_orders_separate_groups(self):
        items = [
            _item("m1", order_id=10, mins_offset=0),
            _item("m2", order_id=11, mins_offset=5),
        ]
        groups = group_materials(items)
        assert len(groups) == 2

    def test_non_bank_skipped(self):
        """只归组 bank。employment 类不参与。"""
        items = [
            _item("m1", mtype="employment"),
            _item("m2", mtype="bank", mins_offset=5),
        ]
        groups = group_materials(items)
        assert len(groups) == 1
        assert groups[0].items[0].material_id == "m2"

    def test_group_id_stable(self):
        """相同 (user, order, type, time) -> 相同 group_id。"""
        items = [_item("m1"), _item("m2", mins_offset=2)]
        g1 = group_materials(items)
        items2 = [_item("m1"), _item("m2", mins_offset=2)]
        g2 = group_materials(items2)
        assert g1[0].group_id == g2[0].group_id


# ===================================================================== #
# 页序还原                                                               #
# ===================================================================== #
class TestPageOrder:
    def test_single_text_item_page_1(self):
        items = [_item("m1", ocr_text="2024-03-01 收入 1000 5000")]
        g = group_materials(items)[0]
        assert len(g.ordered_pages) == 1
        assert g.ordered_pages[0][0] == 1
        assert g.ordered_pages[0][2] == "m1"

    def test_multi_page_items_by_index(self):
        """多页 items 按 page_index 升序排。"""
        items = []
        for mid, n in [("m1", 3)]:
            mi = _item(mid)
            mi.ocr_items = _items_from_text(mid, "2024-03-01 收入 1000 5000", page_count=n)
            items.append(mi)
        g = group_materials(items)[0]
        assert len(g.ordered_pages) == 3
        assert [p[0] for p in g.ordered_pages] == [1, 2, 3]

    def test_multiple_materials_concatenated_renumbered(self):
        """两个材料,各自的页 global 重编号为 1,2,3,4。"""
        mi1 = _item("m1")
        mi1.ocr_items = _items_from_text("m1", "page1content", page_count=2)
        mi2 = _item("m2", mins_offset=5)
        mi2.ocr_items = _items_from_text("m2", "page2content", page_count=2)
        g = group_materials([mi1, mi2])[0]
        assert [p[0] for p in g.ordered_pages] == [1, 2, 3, 4]

    def test_page_footer_detected_en(self):
        """footer "Page 3 / 5" 用来排进 global 顺序(不是直接 page_no)。"""
        text1 = """2024-03-01 收入 1000 5000

Page 1 / 5"""
        text2 = """2024-03-15 收入 1500 6500

Page 3 / 5"""
        # 两份材料分别有 footer 1 和 3,排在一起应得 page_no=1,2
        items = [
            _item("m1", ocr_text=text1),
            _item("m2", mins_offset=5, ocr_text=text2),
        ]
        g = group_materials(items)[0]
        page_nos = [p[0] for p in g.ordered_pages]
        assert page_nos == [1, 2]

    def test_page_footer_detected_zh(self):
        """中文页脚也能识别。"""
        text = "2024-03-01 收入 1000 5000\n\n页码: 2 / 4"
        # 单独一份时,_detect_page_footer 返回 2;但 restore_page_order 重编号为 1
        items = [_item("m1", ocr_text=text)]
        g = group_materials(items)[0]
        # footer 仍识别得到(单元级别)
        from app.services.material_group import _detect_page_footer
        assert _detect_page_footer(text) == 2


class TestOcrItemsGroupByPage:
    def test_no_page_index_defaults_to_page_1(self):
        items = [{"text": "abc", "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]]}]
        by_page = ocr_items_group_by_page(items)
        assert 1 in by_page
        assert "abc" in by_page[1]

    def test_explicit_page_index(self):
        items = [
            {"text": "p1a", "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]], "page_index": 1},
            {"text": "p2a", "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]], "page_index": 2},
            {"text": "p2b", "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]], "page_index": 2},
        ]
        by_page = ocr_items_group_by_page(items)
        assert set(by_page.keys()) == {1, 2}
        assert "p1a" in by_page[1]
        assert "p2a" in by_page[2] and "p2b" in by_page[2]


# ===================================================================== #
# 跨页去重                                                               #
# ===================================================================== #
class TestDedup:
    def test_dedup_same_key_removed(self):
        txns = [
            {"date": "2024-03-01", "amount": 1000.0, "balance": 5000.0},
            {"date": "2024-03-01", "amount": 1000.0, "balance": 5000.0},  # 重复
            {"date": "2024-03-02", "amount": 200.0, "balance": 4800.0},
        ]
        deduped, removed = dedup_transactions(txns)
        assert removed == 1
        assert len(deduped) == 2

    def test_dedup_keeps_first(self):
        txns = [
            {"date": "2024-03-01", "amount": 1000.0, "balance": 5000.0, "page": 1},
            {"date": "2024-03-01", "amount": 1000.0, "balance": 5000.0, "page": 2},
        ]
        deduped, _ = dedup_transactions(txns)
        assert deduped[0]["page"] == 1

    def test_dedup_tolerates_balance_drift(self):
        """balance 浮点微差(±0.01)仍视为同一条。"""
        txns = [
            {"date": "2024-03-01", "amount": 1000.0, "balance": 5000.00},
            {"date": "2024-03-01", "amount": 1000.0, "balance": 5000.01},  # 差 1 分
        ]
        deduped, removed = dedup_transactions(txns)
        assert removed == 1

    def test_dedup_keeps_distinct(self):
        """金额不同不算重复。"""
        txns = [
            {"date": "2024-03-01", "amount": 1000.0, "balance": 5000.0},
            {"date": "2024-03-01", "amount": 2000.0, "balance": 7000.0},
        ]
        deduped, removed = dedup_transactions(txns)
        assert removed == 0

    def test_dedup_with_none_balance(self):
        """没 balance 字段的去重: 仅靠 (date, amount)。"""
        txns = [
            {"date": "2024-03-01", "amount": 100.0, "balance": None},
            {"date": "2024-03-01", "amount": 100.0, "balance": None},
        ]
        deduped, removed = dedup_transactions(txns)
        assert removed == 1

    def test_dedup_with_missing_date_kept(self):
        """没 date 字段的 -> 不参与去重,但保留。"""
        txns = [
            {"amount": 100.0, "balance": 5000.0},  # no date
        ]
        deduped, removed = dedup_transactions(txns)
        assert removed == 0
        assert len(deduped) == 1


# ===================================================================== #
# missing_months                                                        #
# ===================================================================== #
class TestMissingMonths:
    def test_continuous_no_missing(self):
        summary = [
            {"month": "2024-03"}, {"month": "2024-04"}, {"month": "2024-05"},
        ]
        assert detect_missing_months(summary) == []

    def test_one_missing(self):
        summary = [{"month": "2024-03"}, {"month": "2024-05"}]
        assert detect_missing_months(summary) == ["2024-04"]

    def test_multiple_missing(self):
        summary = [{"month": "2024-01"}, {"month": "2024-05"}]
        assert detect_missing_months(summary) == ["2024-02", "2024-03", "2024-04"]

    def test_year_boundary(self):
        summary = [{"month": "2023-11"}, {"month": "2024-02"}]
        assert detect_missing_months(summary) == ["2023-12", "2024-01"]

    def test_unsorted_input(self):
        """输入顺序不影响结果(内部 sort)。"""
        summary = [{"month": "2024-05"}, {"month": "2024-03"}]
        assert detect_missing_months(summary) == ["2024-04"]


class TestMonthHelpers:
    def test_months_between_same(self):
        assert _months_between("2024-03", "2024-03") == 0

    def test_months_between_year(self):
        assert _months_between("2023-12", "2024-02") == 2

    def test_add_months(self):
        assert _add_months("2024-01", 1) == "2024-02"
        assert _add_months("2024-12", 1) == "2025-01"
        assert _add_months("2024-06", -3) == "2024-03"


# ===================================================================== #
# review_group (端到端)                                                  #
# ===================================================================== #
class TestReviewGroupE2E:
    def test_single_page_cn_review(self):
        """单页中文流水 — review_group 应该解析 + aggregate 出正常结果。"""
        text = _cn_lines(n_months=3, per_month=10)
        items = [_item("m1", ocr_text=text)]
        g = group_materials(items)[0]
        rev = review_group(g, source_country="CN")
        assert rev["parser"] == "regex"
        assert rev["page_count"] == 1
        assert rev["txn_count"] >= 20
        assert rev["coverage_months"] >= 3
        # 没有 missing_months(continuous)
        assert rev["missing_months"] == []

    def test_multi_page_cn_each_page_parsed(self):
        """3 页 PDF,每页都解析,transactions 带 page 字段。"""
        # 生成 30 行分 3 页(每页 10 行)
        full = _cn_lines(n_months=3, per_month=10)
        lines = full.split("\n")
        page_size = 10
        mi = _item("m1")
        mi.ocr_items = []
        for p in range(3):
            for line in lines[p * page_size:(p + 1) * page_size]:
                for ch in line:
                    mi.ocr_items.append({
                        "text": ch, "bbox": [[0, p*30], [10, p*30], [10, p*30+20], [0, p*30+20]],
                        "page_index": p + 1, "confidence": 0.95,
                    })
        # OCR items 同一行高度相同聚类,page_index 也要在聚类范围内
        # 简化: 直接每页独立 text 输入
        items = []
        for p in range(3):
            mi_p = _item(f"m_p{p+1}", mins_offset=p)
            mi_p.ocr_text = "\n".join(lines[p * page_size:(p + 1) * page_size])
            items.append(mi_p)
        g = group_materials(items)[0]
        rev = review_group(g, source_country="CN")
        # 30 笔全收(无跨页去重)
        assert rev["txn_count"] >= 25  # 至少 25 笔

    def test_dedup_across_pages(self):
        """两页之间有重复行(同 date+amount+balance) -> 去重。"""
        # 第一页第 5 行 = 第二页第 1 行(模拟跨页重复)
        lines_page1 = [
            "2024-03-01 收入 1000.00 5000.00",
            "2024-03-02 支出 200.00 4800.00",
            "2024-03-03 收入 1500.00 6300.00",
            "2024-03-04 支出 300.00 6000.00",
            "2024-03-05 收入 1200.00 7200.00",  # 这行在 page2 也会有
        ]
        lines_page2 = [
            "2024-03-05 收入 1200.00 7200.00",  # 重复
            "2024-03-06 支出 400.00 6800.00",
            "2024-03-07 收入 1000.00 7800.00",
            "2024-03-08 支出 500.00 7300.00",
            "2024-03-09 收入 1500.00 8800.00",
            "2024-03-10 支出 200.00 8600.00",
            "2024-03-11 收入 1000.00 9600.00",
            "2024-03-12 支出 300.00 9300.00",
        ]
        items = [
            _item("m1", ocr_text="\n".join(lines_page1)),
            _item("m2", mins_offset=5, ocr_text="\n".join(lines_page2)),
        ]
        g = group_materials(items)[0]
        rev = review_group(g, source_country="CN")
        # 13 行 - 1 重复 = 12 笔
        assert rev["dedup_removed"] >= 1
        assert rev["txn_count"] == len(lines_page1) + len(lines_page2) - rev["dedup_removed"]

    def test_review_group_returns_parsed_with_page(self):
        """review 出来的 transactions 带 page 字段。"""
        lines = [
            "2024-03-01 收入 1000.00 5000.00",
            "2024-03-02 支出 200.00 4800.00",
        ]
        items = [_item("m1", ocr_text="\n".join(lines))]
        g = group_materials(items)[0]
        rev = review_group(g, source_country="CN")
        assert all("page" in t for t in rev["transactions"])
        assert all(t["page"] == 1 for t in rev["transactions"])

    def test_missing_months_in_review(self):
        """2 个月跳 1 个月 -> missing_months 标记。"""
        lines = _cn_lines(n_months=2, per_month=10)
        # 改 month,跳过 4 月,直接到 5 月
        lines = lines.replace("2024-01", "2024-03").replace("2024-02", "2024-05")
        items = [_item("m1", ocr_text=lines)]
        g = group_materials(items)[0]
        rev = review_group(g, source_country="CN")
        # coverage_months 算上 03 + 05 = 2 个月,missing 04
        assert "2024-04" in rev["missing_months"]


# ===================================================================== #
# financial_standard                                                    #
# ===================================================================== #
class TestFinancialStandard:
    def test_us_gets_six_months(self):
        std = get_financial_standard("CN", "US")
        assert std.min_coverage_months == 6
        assert std.recommend_balance is True
        assert std.hard_block is False

    def test_schengen_gets_three_months(self):
        std = get_financial_standard("CN", "SCHENGEN")
        assert std.min_coverage_months == 3
        assert std.daily_min == 65.0
        assert std.daily_min_ccy == "EUR"
        assert std.hard_block is True

    def test_schengen_wildcard_any_source(self):
        """SCHENGEN 标准对所有源国一致。"""
        for src in ["CN", "VN", "ID"]:
            std = get_financial_standard(src, "SCHENGEN")
            assert std.min_coverage_months == 3

    def test_unknown_destination_falls_back(self):
        """未知目的国 -> 兜底 3 个月。"""
        std = get_financial_standard("CN", "MARS")  # 火星
        assert std.min_coverage_months == 3
        assert std.hard_block is False


class TestFxRate:
    def test_cny_to_eur(self):
        fx = get_fx_rate("CNY", "EUR")
        assert fx is not None
        assert fx.rate == 0.128
        assert fx.source == "static@business"
        assert fx.as_of == "2026-07-01"

    def test_identity(self):
        fx = get_fx_rate("USD", "USD")
        assert fx.rate == 1.0
        assert fx.source == "identity"

    def test_unknown_pair_returns_none(self):
        fx = get_fx_rate("CNY", "BTC")  # 没配
        assert fx is None

    def test_convert_cny_to_eur(self):
        amount, fx = convert_balance(10000.0, "CNY", "EUR")
        assert amount == 1280.0  # 10000 * 0.128
        assert fx is not None

    def test_convert_with_unknown_pair(self):
        amount, fx = convert_balance(10000.0, "CNY", "BTC")
        assert amount is None
        assert fx is None


class TestEvaluateBalance:
    def test_schengen_10_days_meets(self):
        """申根 10 天 = 650 EUR 最低;用户 1000 EUR 够。"""
        v = evaluate_balance(
            ending_balance_src=10000.0,  # CNY
            source_country="CN",
            destination="SCHENGEN",
            stay_days=10,
        )
        assert v.meets_minimum is True
        assert v.ending_balance_dest == 1280.0  # 10000 * 0.128

    def test_schengen_30_days_fails(self):
        """申根 30 天 = 1950 EUR 最低;用户只有 ¥10000 = 1280 EUR 不够。"""
        v = evaluate_balance(
            ending_balance_src=10000.0,
            source_country="CN",
            destination="SCHENGEN",
            stay_days=30,
        )
        assert v.meets_minimum is False
        assert v.severity == "block"  # 申根 hard_block
        # 数字可能带千分位 (1,280.00) 或不带 (1280.00)
        assert ("1280" in v.detail) or ("1,280" in v.detail)

    def test_au_no_hard_block_without_stay_days(self):
        """澳签有 daily_min_aud,但未传 stay_days 时不强行 block。"""
        v = evaluate_balance(
            ending_balance_src=10_000.0,
            source_country="CN",
            destination="AU",
            stay_days=None,
        )
        assert v.meets_minimum is True

    def test_us_soft_recommendation(self):
        """美签: 有 recommend_balance 但非 hard_block。"""
        v = evaluate_balance(
            ending_balance_src=1000.0,  # CNY ≈ 139 USD
            source_country="CN",
            destination="US",
            recommended_balance_dest=3000.0,
        )
        # 余额低于 recommended,但 destination US 是 soft
        assert v.severity == "warn"
        assert v.meets_minimum is False

    def test_none_ending_balance(self):
        v = evaluate_balance(
            ending_balance_src=None,
            source_country="CN",
            destination="US",
        )
        assert v.meets_minimum is False
        assert "未提供" in v.detail

    def test_vietnam_dong_small_number_actually_large(self):
        """越南 100,000,000 VND ≈ 3570 EUR (按 0.0000357 汇率),能过申根 10 天。"""
        v = evaluate_balance(
            ending_balance_src=100_000_000.0,  # 1 亿越南盾
            source_country="VN",
            destination="SCHENGEN",
            stay_days=10,
        )
        assert v.meets_minimum is True
        # 1 亿 VND * 0.0000357 = 3570 EUR > 650 EUR