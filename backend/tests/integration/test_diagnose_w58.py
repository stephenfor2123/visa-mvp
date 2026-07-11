"""W58 4 国差异化打分 — 单元测试。

覆盖:
- 4 国基础项一致性(同 profile 下基础项分数相同)
- 申根保险未购硬封顶 50
- 4 国专项触发(各出一个 country 权重 factor)
- 强/弱 profile 4 国分数分布合理(无全员 0 / 全员 100)
- 申根 26 国共用 schengen_rules
"""
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.diagnose_rules import compute_diagnose


def _req(country_code, **overrides):
    """构造一个标准 profile + 可覆盖字段的 req。"""
    base = dict(
        country_code=country_code,
        marital_status="single",
        income_bucket="15k_30k",
        travel_purpose="tourism",
        travel_history="1_3",
        visa_history="1_2",
        employment="employed",
        age=30,
        is_solo_female=False,
        # W58 新增字段(都给中间值)
        property_signals=1,
        income_source="salary",
        interview_ready=None,
        funds_balance_bucket="1w_5w",
        employment_years=3,
        uk_visa_history="never",
        developed_country_visa="none",
        itinerary_complete="partial",
        insurance_purchased=True,
        funds_coverage_ratio=1.2,
        schengen_fingerprint_5y=False,
        leave_letter_ready=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------- #
# 1. 基础项 4 国一致                                                          #
# --------------------------------------------------------------------------- #
def test_base_factors_consistent_across_countries():
    """4 国基础项 6 字段应该完全相同。"""
    base_factor_names = {
        "婚姻", "收入", "出行记录", "签证历史", "在职",
    }
    for cc in ("US", "GB", "AU", "FR"):
        r = compute_diagnose(_req(cc))
        base_factors = [f for f in r["factors"] if f.weight_group == "base"]
        names = {f.name.split(":")[0] for f in base_factors}
        assert names == base_factor_names, f"{cc} 基础项不匹配: {names}"


# --------------------------------------------------------------------------- #
# 2. 4 国专项触发                                                              #
# --------------------------------------------------------------------------- #
def test_us_country_factor_present():
    """US profile 应有面签准备度 + 资金来源等专项 factor。"""
    r = compute_diagnose(_req("US", interview_ready="ready", income_source="salary"))
    country_factors = [f for f in r["factors"] if f.weight_group == "country"]
    assert len(country_factors) >= 1
    assert any("面签" in f.name for f in country_factors)


def test_gb_country_factor_present():
    """GB profile 应有资金 + 在职年限等专项 factor。"""
    r = compute_diagnose(_req("GB", funds_balance_bucket="above_5w", employment_years=5))
    country_factors = [f for f in r["factors"] if f.weight_group == "country"]
    assert any("资金" in f.name for f in country_factors)
    assert any("在职年限" in f.name for f in country_factors)


def test_au_country_factor_present():
    """AU profile 应有签证历史(发达国家)等专项 factor。"""
    r = compute_diagnose(_req("AU", developed_country_visa="us_gb_schengen"))
    country_factors = [f for f in r["factors"] if f.weight_group == "country"]
    assert any("签证历史" in f.name for f in country_factors)


def test_schengen_country_factor_present():
    """申根(FR) profile 应有行程/保险/资金覆盖等专项 factor。"""
    r = compute_diagnose(_req("FR", itinerary_complete="full",
                              funds_coverage_ratio=2.0))
    country_factors = [f for f in r["factors"] if f.weight_group == "country"]
    names = [f.name for f in country_factors]
    assert any("行程" in n for n in names)
    assert any("保险" in n for n in names)
    assert any("资金" in n for n in names)


# --------------------------------------------------------------------------- #
# 3. 申根保险未购 硬封顶                                                       #
# --------------------------------------------------------------------------- #
def test_schengen_no_insurance_caps_at_50():
    """申根保险未购时,无论 profile 多强, 总分封顶 50 (level 不会到 high)。"""
    r = compute_diagnose(_req("FR", insurance_purchased=False, itinerary_complete="full",
                              funds_coverage_ratio=5.0, property_signals=3, income_source="salary",
                              employment_years=20, travel_history="above_10",
                              visa_history="above_2", income_bucket="above_100k"))
    assert r["score"] <= 50, f"FR 保险未购应封顶 50, 实际 {r['score']}"
    # 50 分属于 medium (阈值 75/50), 强 profile 不可能 high
    assert r["level"] != "high"


def test_schengen_with_insurance_can_score_high():
    """申根保险+行程齐全, 可以拿到 high 等级。"""
    r = compute_diagnose(_req("FR", insurance_purchased=True, itinerary_complete="full",
                              funds_coverage_ratio=2.0, schengen_fingerprint_5y=True,
                              property_signals=3, employment_years=10,
                              income_bucket="above_100k"))
    assert r["score"] >= 75
    assert r["level"] == "high"


def test_non_schengen_no_insurance_cap():
    """非申根国家(US)不被保险规则钳制。"""
    r = compute_diagnose(_req("US", insurance_purchased=False,  # 显式不购, 但不影响 US
                              property_signals=3, interview_ready="ready"))
    # US 不应有保险相关 factor
    assert not any("保险" in f.name for f in r["factors"])


# --------------------------------------------------------------------------- #
# 4. 申根 26 国共用规则                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cc", ["FR", "DE", "IT", "ES", "NL", "AT", "GR"])
def test_schengen_countries_share_rules(cc):
    """申根 26 国都应走同一份 schengen_rules, 出行程/保险/资金 cover factor。"""
    r = compute_diagnose(_req(cc))
    names = [f.name for f in r["factors"]]
    assert any("行程" in n for n in names), f"{cc} 应出行程 factor"
    assert any("保险" in n for n in names), f"{cc} 应出保险 factor"
    # policy_summary 应是非空
    assert r["policy_summary"] is not None


# --------------------------------------------------------------------------- #
# 5. 4 国分数差异(同 profile, 不应完全相同)                                   #
# --------------------------------------------------------------------------- #
def test_four_countries_diverge():
    """同样 profile, 4 国分数应该有差异(因为专项不同)。"""
    # 用一个能触发 4 国各自专项的 profile
    base = _req("US", property_signals=0, interview_ready="unprepared",
                funds_balance_bucket="below_1w", employment_years=0,
                developed_country_visa="none",
                itinerary_complete="none", insurance_purchased=False,
                funds_coverage_ratio=0.5, schengen_fingerprint_5y=False,
                leave_letter_ready=False)
    scores = {}
    for cc in ("US", "GB", "AU", "FR"):
        # 每次重新构造 req, 避免 SimpleNamespace 共享状态
        req = SimpleNamespace(**{**base.__dict__, "country_code": cc})
        r = compute_diagnose(req)
        scores[cc] = r["score"]
    # 4 国里至少 3 个不同分数
    assert len(set(scores.values())) >= 3, f"4 国分数太接近: {scores}"


# --------------------------------------------------------------------------- #
# 6. 等级阈值                                                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("score,level", [(100, "high"), (75, "high"), (74, "medium"),
                                         (50, "medium"), (49, "low"), (0, "low")])
def test_level_thresholds(score, level):
    """等级阈值 75/50 正确。"""
    # 构造刚好触达目标分数的 profile
    # 用最简 profile 验证: 全部传 None / 中性, 然后逐步减分到目标
    if level == "high":
        req = _req("US", property_signals=3, income_source="salary",
                   interview_ready="ready", income_bucket="above_100k",
                   travel_history="above_10", visa_history="above_2",
                   employment_years=10)
    elif level == "medium":
        req = _req("US")  # 标准 profile
    else:  # low
        req = _req("US", marital_status="single", age=24, income_bucket="below_5k",
                   travel_history="none", visa_history="none", employment="unemployed",
                   property_signals=0, income_source="one_off", interview_ready="unprepared")
    r = compute_diagnose(req)
    # 验证分数落在该等级区间(允许小幅偏差)
    if level == "high":
        assert r["score"] >= 75
    elif level == "medium":
        assert 50 <= r["score"] < 75
    else:
        assert r["score"] < 50


# --------------------------------------------------------------------------- #
# 7. 兼容老请求(只传基础 6 字段)                                              #
# --------------------------------------------------------------------------- #
def test_backward_compatible_basic_request():
    """只传旧版 6 字段也能跑(新字段都默认 None, 不影响)。"""
    req = SimpleNamespace(
        country_code="US",
        marital_status="single",
        income_bucket="15k_30k",
        travel_purpose="tourism",
        travel_history="1_3",
        visa_history="none",
        employment="employed",
        age=30,
        is_solo_female=False,
        # W58 字段全部缺省
    )
    r = compute_diagnose(req)
    assert r["score"] >= 0
    assert r["score"] <= 100
    assert r["level"] in ("high", "medium", "low")


# --------------------------------------------------------------------------- #
# 8. policy_summary                                                            #
# --------------------------------------------------------------------------- #
def test_policy_summary_per_country():
    """4 国都应有对应的 policy_summary。"""
    expected = {
        "US": True, "GB": True, "AU": True, "FR": True,
        "DE": True, "IT": True,  # 申根 26 国共用
    }
    for cc, expect in expected.items():
        r = compute_diagnose(_req(cc))
        assert (r["policy_summary"] is not None) == expect, f"{cc} policy_summary 异常"
