"""VisaDiagnoser completeness rules — W36 regression.

Before W36, `_REQUIRED` only recognized `material_type == "other"` for
financial/itinerary requirements. The material wizard now tags these with
specific types (bank/flight/hotel), which used to be reported as "missing"
even when genuinely uploaded. These tests lock in the fix.
"""
from __future__ import annotations

from app.services.visa_diagnoser import VisaDiagnoser


def _material(material_type: str, mid: int = 1) -> dict:
    return {"id": mid, "material_type": material_type, "ocr_status": "done", "ocr_result": None}


class TestFinancialRequirementAcceptsBankType:
    def test_bank_type_satisfies_us_financial(self):
        materials = [_material("passport"), _material("photo"), _material("form"), _material("bank")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.financial" not in codes

    def test_other_type_still_satisfies_us_financial(self):
        # Backward-compat: generic "other" upload must still count.
        materials = [_material("passport"), _material("photo"), _material("form"), _material("other")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.financial" not in codes

    def test_missing_financial_still_flagged(self):
        materials = [_material("passport"), _material("photo"), _material("form")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.financial" in codes


class TestItineraryRequirementAcceptsFlightHotelTypes:
    def test_flight_type_satisfies_us_itinerary(self):
        materials = [_material("passport"), _material("photo"), _material("form"), _material("flight")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.itinerary" not in codes

    def test_hotel_type_satisfies_us_itinerary(self):
        materials = [_material("passport"), _material("photo"), _material("form"), _material("hotel")]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "us.itinerary" not in codes


class TestPassportExpiryReadsFlatOcrResult:
    """W39 regression: the only code path that persists Material.ocr_result
    (POST /materials/{id}/ocr) writes a FLAT dict, e.g. {"expiry": "2030-12-31",
    "passport_no": "..."}. VisaDiagnoser used to read ocr_result["fields"]
    (a nested shape no producer ever wrote), so ocr_fields was always {} and
    every passport was flagged as missing its expiry even when OCR found one.
    """

    def test_flat_ocr_result_with_expiry_does_not_flag_missing(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.expiry_missing" not in codes

    def test_missing_expiry_still_flagged_with_params(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        issue = next(i for i in out.issues if i.code == "passport.expiry_missing")
        assert issue.related_material_id == 1

    def test_short_expiry_flagged_with_structured_params(self):
        # W39: title/detail used to be pre-rendered zh-CN only; params lets a
        # frontend re-render the message in its own locale.
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2026-08-01"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        issue = next(i for i in out.issues if i.code == "passport.expiry_short")
        assert issue.params["expiry"] == "2026-08-01"
        assert issue.params["min_months"] == VisaDiagnoser.PASSPORT_MIN_VALIDITY_MONTHS
        assert isinstance(issue.params["months_left"], int)


class TestPassportNotDetectedVsExpiryMissing:
    """W45: OCR finding nothing passport-like in the image (is_passport_doc
    False) is a different failure from OCR reading a real passport page but
    missing the expiry field — users were confused by the generic
    "expiry field missing" message when the upload wasn't a passport at all.
    """

    def test_is_passport_doc_false_uses_not_detected_code(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"is_passport_doc": False, "raw_text": ""}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.not_detected" in codes
        assert "passport.expiry_missing" not in codes

    def test_is_passport_doc_true_but_no_expiry_uses_expiry_missing_code(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"is_passport_doc": True, "passport_no": "E12345678"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.expiry_missing" in codes
        assert "passport.not_detected" not in codes

    def test_missing_is_passport_doc_key_defaults_to_expiry_missing(self):
        # backward-compat: older persisted ocr_result rows never had this key
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678"}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "passport.expiry_missing" in codes


class TestBankStatementCompleteness:
    """W51: VisaDiagnoser 必须能基于 bank_statement_parser 的输出做诊断。

    ocr_result 里塞 {parser, txn_count, coverage_months, monthly_income_avg,
    large_inflows, ...}这些由 bank_statement_parser 写入的字段。
    """

    def _bank(self, mid: int = 1, **ocr_fields) -> dict:
        return {
            "id": mid,
            "material_type": "bank",
            "ocr_status": "done",
            "ocr_result": ocr_fields or None,
        }

    def test_unparseable_bank_flags_warning(self):
        # parser 标记 none 或空 + 0 笔 → 提示用户人工补
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank(mid=2, parser="none", txn_count=0),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.unparseable" in codes
        issue = next(i for i in out.issues if i.code == "bank.unparseable")
        assert issue.severity == "warning"
        assert issue.title_key == "diagnose.bank_unparseable_title"
        assert issue.related_material_id == 2

    def test_short_coverage_below_3_months_flags_warning(self):
        # 2 个月 — 不足
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank(mid=2, parser="regex", txn_count=12, coverage_months=2),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.coverage_short" in codes
        issue = next(i for i in out.issues if i.code == "bank.coverage_short")
        assert issue.params["months"] == 2

    def test_adequate_coverage_3plus_months_is_positive(self):
        # 6 个月 + 120 笔 + 月入 1.2 万 = 全部达标
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank(mid=2, parser="regex", txn_count=142, coverage_months=6,
                       monthly_income_avg=12000.0),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.coverage_short" not in codes
        assert "bank.unparseable" not in codes
        assert "bank.income_low" not in codes
        # positives 应该提到月数
        assert any("6" in p and "覆盖" in p for p in out.positives)
        assert any("142" in p and "交易" in p for p in out.positives)

    def test_low_income_monthly_triggers_warning(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank(mid=2, parser="regex", txn_count=80, coverage_months=5,
                       monthly_income_avg=1500.0),  # 低于 3000
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.income_low" in codes
        issue = next(i for i in out.issues if i.code == "bank.income_low")
        assert issue.params["monthly_income"] == 1500.0

    def test_large_inflows_trigger_warning(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank(mid=2, parser="regex", txn_count=80, coverage_months=6,
                       monthly_income_avg=10000.0,
                       large_inflows=[
                           {"date": "2024-06-15", "amount": 80000.0, "description": "他行汇入"},
                           {"date": "2024-07-10", "amount": 60000.0, "description": "现金存入"},
                       ]),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.large_inflow" in codes
        issue = next(i for i in out.issues if i.code == "bank.large_inflow")
        assert issue.params["count"] == 2

    def test_no_ocr_result_yet_treated_as_unparseable(self):
        # 用户上传了银行流水但还没跑 OCR — 应该提示需要跑 OCR (走 unparseable)
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            {"id": 2, "material_type": "bank", "ocr_status": "pending",
             "ocr_result": None},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.unparseable" in codes  # ocr_status: pending 也算 unparseable


class TestBankIncomeGap:
    """W52: visa_diagnoser 应当读 income_gaps 字段给出 bank.income_gap 诊断。"""

    def _passport(self) -> dict:
        return {"id": 1, "material_type": "passport", "ocr_status": "done",
                "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}}

    def test_one_month_gap_flagged(self):
        materials = [
            self._passport(),
            {"id": 2, "material_type": "bank", "ocr_status": "done",
             "ocr_result": {
                 "parser": "regex", "txn_count": 50, "coverage_months": 6,
                 "monthly_income_avg": 11000.0, "ending_balance": 40000.0,
                 "income_gaps": [{"start_month": "2024-09", "end_month": "2024-09", "gap_months": 1}],
             }},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.income_gap" in codes
        issue = next(i for i in out.issues if i.code == "bank.income_gap")
        assert issue.severity == "warning"
        assert issue.params["gap_months"] == 1
        assert issue.params["start_month"] == "2024-09"
        assert "1" in issue.title

    def test_multi_month_gap_takes_worst_segment(self):
        # 2 段 gap,取最长的那段(2 个月)做为主标题
        materials = [
            self._passport(),
            {"id": 2, "material_type": "bank", "ocr_status": "done",
             "ocr_result": {
                 "parser": "regex", "txn_count": 50, "coverage_months": 8,
                 "monthly_income_avg": 11000.0, "ending_balance": 40000.0,
                 "income_gaps": [
                     {"start_month": "2024-08", "end_month": "2024-08", "gap_months": 1},
                     {"start_month": "2024-11", "end_month": "2024-12", "gap_months": 2},
                 ],
             }},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        issue = next(i for i in out.issues if i.code == "bank.income_gap")
        assert issue.params["gap_months"] == 2
        assert issue.params["start_month"] == "2024-11"
        assert issue.params["end_month"] == "2024-12"
        assert issue.params["gap_count"] == 2

    def test_no_gap_no_issue(self):
        materials = [
            self._passport(),
            {"id": 2, "material_type": "bank", "ocr_status": "done",
             "ocr_result": {
                 "parser": "regex", "txn_count": 80, "coverage_months": 6,
                 "monthly_income_avg": 12000.0, "ending_balance": 50000.0,
                 "income_gaps": [],
             }},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.income_gap" not in codes

    def test_missing_income_gaps_field_no_crash(self):
        # 老数据可能没 income_gaps 字段,保证向后兼容(直接跳过,不出 issue)
        materials = [
            self._passport(),
            {"id": 2, "material_type": "bank", "ocr_status": "done",
             "ocr_result": {
                 "parser": "regex", "txn_count": 80, "coverage_months": 6,
                 "monthly_income_avg": 12000.0, "ending_balance": 50000.0,
                 # 注意: 没有 income_gaps 字段
             }},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US", visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.income_gap" not in codes


class TestBankBalanceCoverage:
    """W52: visa_diagnoser 应当基于 ending_balance vs 行程预算做诊断。"""

    def _passport(self) -> dict:
        return {"id": 1, "material_type": "passport", "ocr_status": "done",
                "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}}

    def _bank(self, balance: float) -> dict:
        return {"id": 2, "material_type": "bank", "ocr_status": "done",
                "ocr_result": {
                    "parser": "regex", "txn_count": 80, "coverage_months": 6,
                    "monthly_income_avg": 12000.0,
                    "ending_balance": balance,
                }}

    def test_balance_too_low_flagged(self):
        # 余额 5000,10 天行程 + 没填机票酒店 → 预算 ~8000+11000=19000,不足
        materials = [
            self._passport(),
            self._bank(5000.0),
        ]
        fields = {"stay_days": 10, "flight_no": "CA1234", "hotel_name": "Hotel"}
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism", fields=fields)
        codes = [i.code for i in out.issues]
        assert "bank.balance_coverage" in codes
        issue = next(i for i in out.issues if i.code == "bank.balance_coverage")
        assert issue.params["ending_balance"] == 5000.0
        assert issue.params["stay_days"] == 10
        assert issue.params["ratio"] < 1.0
        assert issue.severity == "warning"

    def test_balance_adequate_positive(self):
        # 余额 50000,7 天行程 + 有机票酒店 → 预算 ~6000+7700=13700, ratio > 2
        materials = [
            self._passport(),
            self._bank(50000.0),
        ]
        fields = {"stay_days": 7, "flight_no": "CA1234", "hotel_name": "Hotel"}
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism", fields=fields)
        codes = [i.code for i in out.issues]
        assert "bank.balance_coverage" not in codes
        # 应当出现 positive
        assert any("充裕" in p or "覆盖" in p for p in out.positives)

    def test_balance_marginal_warning(self):
        # 余额 15000,7 天 → 预算 ~13700, ratio 1.09, 触发 warning (不阻断)
        materials = [
            self._passport(),
            self._bank(15000.0),
        ]
        fields = {"stay_days": 7, "flight_no": "CA1234"}
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism", fields=fields)
        # 1.0 <= ratio < 2.0 → 不报 issue,只 positive
        codes = [i.code for i in out.issues]
        assert "bank.balance_coverage" not in codes
        assert any("覆盖" in p for p in out.positives)

    def test_no_stay_days_skipped(self):
        # 没有 stay_days → 跳过这条规则
        materials = [
            self._passport(),
            self._bank(5000.0),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism", fields={})
        codes = [i.code for i in out.issues]
        assert "bank.balance_coverage" not in codes

    def test_no_bank_material_skipped(self):
        # 没有 bank material → 跳过这条规则
        materials = [self._passport()]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism", fields={"stay_days": 7})
        codes = [i.code for i in out.issues]
        assert "bank.balance_coverage" not in codes


class TestBankBalanceChainW53:
    """W53: visa_diagnoser 接入 balance_chain_check,余额链断链报 critical/warn。

    ocr_result 里塞 transactions[] (含 balance 字段) 模拟 OCR 完整结果。
    """

    def _bank_with_txns(self, mid: int, txns, **extra) -> dict:
        return {
            "id": mid,
            "material_type": "bank",
            "ocr_status": "done",
            "ocr_result": {"parser": "regex", "txn_count": len(txns),
                           "coverage_months": 3, "transactions": txns, **extra},
        }

    def _txn(self, date, amount, direction, balance=None, page=None):
        return {
            "date": date, "amount": amount, "direction": direction,
            "balance": balance, "page": page,
            "description": "mock", "currency": "CNY",
        }

    def test_balance_chain_pass_adds_positive(self):
        """余额链连续 → positives 加一条。"""
        txns = [
            self._txn("2024-03-01", 1000.0, "in", balance=1000.0),
            self._txn("2024-03-02", 200.0, "out", balance=800.0),
            self._txn("2024-03-03", 50.0, "in", balance=850.0),
        ]
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_txns(2, txns),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        assert any("余额链" in p and "通过" in p for p in out.positives)
        assert not any(i.code == "bank.balance_chain_break" for i in out.issues)

    def test_single_break_flags_warn(self):
        """单笔断链(<5) → severity=warn。"""
        txns = [
            self._txn("2024-03-01", 1000.0, "in", balance=1000.0),
            self._txn("2024-03-02", 200.0, "out", balance=850.0),  # 期望 800
        ]
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_txns(2, txns),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        chain_issues = [i for i in out.issues if i.code == "bank.balance_chain_break"]
        assert len(chain_issues) == 1
        assert chain_issues[0].severity == "warn"

    def test_many_breaks_flag_critical(self):
        """≥5 笔断链 → severity=critical。"""
        txns = [
            self._txn("2024-03-01", 1000.0, "in", balance=1000.0),
        ]
        # 加 6 笔篡改 — 全部 balance=999 (期望 1000±amount)
        for i in range(2, 8):
            txns.append(self._txn(f"2024-03-{i:02d}", 50.0, "out", balance=999.0))
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_txns(2, txns),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        chain_issues = [i for i in out.issues if i.code == "bank.balance_chain_break"]
        assert len(chain_issues) >= 1
        assert chain_issues[0].severity == "critical"

    def test_no_balance_anywhere_does_not_critical(self):
        """A 方案: 没 balance 字段 → 不报 critical,不报任何 break。"""
        txns = [
            self._txn("2024-03-01", 100.0, "in"),
            self._txn("2024-03-02", 50.0, "out"),
            self._txn("2024-03-03", 30.0, "in"),
        ]
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_txns(2, txns),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        assert not any(i.code == "bank.balance_chain_break" for i in out.issues)

    def test_low_coverage_does_not_critical(self):
        """A 方案: balance 覆盖率 < 30% → 不报 critical。"""
        # 10 笔只有 1 笔有 balance
        txns = [self._txn(f"2024-03-{i+1:02d}", 10.0, "in") for i in range(10)]
        txns[0]["balance"] = 100.0
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_txns(2, txns),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        assert not any(i.code == "bank.balance_chain_break" for i in out.issues)


class TestBankMissingMonthsW54:
    """W54: monthly_summary 不连续 → 报 bank.months_missing。"""

    def _bank_with_months(self, mid, missing_months):
        return {
            "id": mid, "material_type": "bank", "ocr_status": "done",
            "ocr_result": {"parser": "regex", "txn_count": 50, "coverage_months": 4,
                           "missing_months": missing_months},
        }

    def test_missing_months_flagged(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_months(2, ["2024-04", "2024-05"]),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.months_missing" in codes
        issue = next(i for i in out.issues if i.code == "bank.months_missing")
        assert issue.params["missing_months"] == ["2024-04", "2024-05"]

    def test_no_missing_no_issue(self):
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_months(2, []),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        assert "bank.months_missing" not in [i.code for i in out.issues]


class TestBankBalanceThresholdW54:
    """W54: ending_balance 按目的国门槛 + 汇率换算后判定。"""

    def _bank_with_balance(self, mid, ending_balance, src="CN"):
        return {
            "id": mid, "material_type": "bank", "ocr_status": "done",
            "ocr_result": {"parser": "regex", "txn_count": 50, "coverage_months": 3,
                           "ending_balance": ending_balance, "source_country": src,
                           "currency": src},
        }

    def test_schengen_30_days_below_threshold_block(self):
        """¥10000 * 30 天申根 < 1950 EUR 最低 → block。"""
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_balance(2, 10000.0),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="SCHENGEN",
                                       visa_type="tourism", fields={"destination": "SCHENGEN", "stay_days": 30})
        codes = [i.code for i in out.issues]
        assert "bank.balance_below_threshold" in codes
        issue = next(i for i in out.issues if i.code == "bank.balance_below_threshold")
        assert issue.severity == "block"  # 申根 hard_block

    def test_schengen_10_days_meets_no_issue(self):
        """¥10000 * 10 天申根 = 1280 EUR > 650 EUR → 不报。"""
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_balance(2, 10000.0),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="SCHENGEN",
                                       visa_type="tourism", fields={"destination": "SCHENGEN", "stay_days": 10})
        codes = [i.code for i in out.issues]
        assert "bank.balance_below_threshold" not in codes

    def test_no_destination_field_skips(self):
        """没有 fields["destination"] → 跳过换算检查。"""
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_balance(2, 100.0),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism", fields={"stay_days": 30})
        assert "bank.balance_below_threshold" not in [i.code for i in out.issues]

    def test_vietnamese_dong_conversion(self):
        """越南 1 亿 VND ≈ 3570 EUR > 650 EUR → 不报。"""
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            self._bank_with_balance(2, 100_000_000.0, src="VN"),
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="SCHENGEN",
                                       visa_type="tourism", fields={"destination": "SCHENGEN", "stay_days": 10})
        assert "bank.balance_below_threshold" not in [i.code for i in out.issues]


class TestBankSuddenInflowW55:
    """W55: visa_diagnoser 接入 detect_sudden_inflows。"""

    def test_sudden_inflow_flagged(self):
        """90 天小进账 + 最后大额 → 报 bank.sudden_inflow。"""
        from datetime import date, timedelta
        txns = []
        end = date(2024, 6, 1)
        for i in range(90):
            d = (end - timedelta(days=i)).isoformat()
            txns.append({"date": d, "amount": 200.0, "direction": "in", "balance": 5000.0,
                         "description": "小进账", "currency": "CNY"})
        txns.append({"date": "2024-06-01", "amount": 50000.0, "direction": "in",
                     "balance": 55000.0, "description": "他行汇入", "currency": "CNY"})
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            {"id": 2, "material_type": "bank", "ocr_status": "done",
             "ocr_result": {"parser": "regex", "txn_count": len(txns),
                            "coverage_months": 3, "transactions": txns}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        codes = [i.code for i in out.issues]
        assert "bank.sudden_inflow" in codes
        issue = next(i for i in out.issues if i.code == "bank.sudden_inflow")
        assert issue.severity == "hard_block"
        assert issue.params["count"] >= 1
        # ocr_fields 里也要能取到 sudden_inflows(给前端报告)
        # (这是 diagnoser 内部字段,只能从 issue.params 取)

    def test_normal_salary_no_sudden(self):
        """稳定月入 1 万不算突击。"""
        txns = []
        for m in range(1, 7):
            for d in [5, 20]:
                txns.append({"date": f"2024-{m:02d}-{d:02d}", "amount": 10000.0,
                             "direction": "in", "balance": 100000.0,
                             "description": "工资", "currency": "CNY"})
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            {"id": 2, "material_type": "bank", "ocr_status": "done",
             "ocr_result": {"parser": "regex", "txn_count": len(txns),
                            "coverage_months": 6, "transactions": txns}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        assert "bank.sudden_inflow" not in [i.code for i in out.issues]

    def test_sudden_inflow_old_too_far_skipped(self):
        """104 天前的突击 → 不报(不在申请前 30 天内)。"""
        from datetime import date, timedelta
        txns = []
        # 申请日 ≈ 2024-06-15; 突击 2024-02-01 (104 天前)
        for d in _date_range_helper("2024-05-15", 100):
            txns.append({"date": d, "amount": 200.0, "direction": "in", "balance": 5000.0,
                         "description": "x", "currency": "CNY"})
        txns.append({"date": "2024-02-01", "amount": 50000.0, "direction": "in",
                     "balance": 55000.0, "description": "老突击", "currency": "CNY"})
        materials = [
            {"id": 1, "material_type": "passport", "ocr_status": "done",
             "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
            {"id": 2, "material_type": "bank", "ocr_status": "done",
             "ocr_result": {"parser": "regex", "txn_count": len(txns),
                            "coverage_months": 4, "transactions": txns}},
        ]
        out = VisaDiagnoser().diagnose(materials=materials, country_code="US",
                                       visa_type="tourism")
        assert "bank.sudden_inflow" not in [i.code for i in out.issues]


def _date_range_helper(end_str, days_back):
    from datetime import date, timedelta
    end = date.fromisoformat(end_str)
    return [(end - timedelta(days=i)).isoformat() for i in range(days_back + 1)]
