"""W46: localize_curated_text — rewrite canonical zh-CN money phrases to the
destination-country local currency before RAG chunking.

Why: previously every country's curated FAQ hardcoded "余额建议 ≥ 5万元",
which made no sense for applicants targeting the US / GB / VN / ID etc.
"""
from app.services.rag.refresh import localize_curated_text


class TestLocalizeCuratedText:
    def test_us_rewrites_balance_to_usd(self):
        text = "近6个月银行流水 (余额建议 ≥ 5万元, 流水显示稳定收入)"
        out = localize_curated_text(text, "US")
        assert "US$7,000" in out
        assert "5万元" not in out

    def test_gb_rewrites_balance_to_gbp(self):
        text = "近6个月银行流水 (余额建议 ≥ 5万元, 流水显示稳定收入)"
        out = localize_curated_text(text, "GB")
        assert "£5,500" in out

    def test_schengen_keeps_30k_eur_insurance_untouched(self):
        # Schengen has a legally-mandated €30,000 minimum written as "3万欧元"
        # — our pattern should not touch it.
        text = "旅行医疗保险 (覆盖申根区, 保额 ≥ 3万欧元, 涵盖整个行程)"
        out = localize_curated_text(text, "FR")
        assert "3万欧元" in out

    def test_vn_rewrites_balance_to_vnd_with_dong_sign(self):
        text = "近6个月银行流水 (余额建议 ≥ 5万元)"
        out = localize_curated_text(text, "VN")
        assert "₫150,000,000" in out

    def test_id_rewrites_balance_to_idr_with_dot_separator(self):
        # Indonesian thousand separator is "."
        text = "近6个月银行流水 (余额建议 ≥ 5万元)"
        out = localize_curated_text(text, "ID")
        assert "Rp 100.000.000" in out

    def test_unknown_country_leaves_text_untouched(self):
        text = "近6个月银行流水 (余额建议 ≥ 5万元)"
        out = localize_curated_text(text, "ZZ")
        assert out == text  # no rewrite

    def test_lowercase_country_code_normalized(self):
        text = "近6个月银行流水 (余额建议 ≥ 5万元)"
        out = localize_curated_text(text, "us")
        assert "US$7,000" in out

    def test_no_balance_phrase_is_a_noop(self):
        text = "签证费：185美元"
        out = localize_curated_text(text, "US")
        assert out == text

    def test_rewrites_insurance_to_country_specific_when_amount_in_wan_yuan(self):
        # The 30万 generic phrase should be rewritten for non-Schengen,
        # non-default countries (US / GB / JP etc.).
        text = "覆盖行程全程，保额 ≥ 30 万元"
        out_us = localize_curated_text(text, "US")
        assert "US$50,000" in out_us
        assert "30 万元" not in out_us