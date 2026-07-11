"""目的国财务门槛 (W54 v1)

按设计稿要求:门槛数值不写死,放配置 + 注明来源日期,由业务同学核实。
代码只做"读配置 → 比较"。

配置维度: (source_country, destination) -> 标准
例:
  ("CN", "US"):     { min_coverage_months: 6, recommend_balance: True }
  ("*", "SCHENGEN"): { min_coverage_months: 3, daily_min_eur: 65 }

汇率换算 (FX)
------------
提供 source_country 货币 → destination 货币的换算。
v1 用静态汇率(每月维护一次),生产可以替换成实时 API。
所有汇率都注明"as_of"日期,业务同学核实。

数据结构
--------
@dataclass FinancialStandard:
    min_coverage_months: int
    recommend_balance: bool = False   # 美签建议余额证明
    daily_min_eur: Optional[float] = None  # 申根每天最低 EUR(用于估算)
    hard_block: bool = False          # 不达标是否直接 block(签证官直接拒)

@dataclass FxRate:
    source_ccy: str   # CNY / VND / IDR / ...
    dest_ccy: str     # EUR / USD / ...
    rate: float       # 1 source_ccy = rate dest_ccy
    as_of: str        # YYYY-MM-DD
    source: str       # 静态表 / api.xxx.com / etc
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# 财务标准 (门槛)                                                      #
# ---------------------------------------------------------------- #
# 来源日期: 2026-07 业务同学核实 (申根按 EUR 65/天估算 ≈ ¥500/天,
# 美签 6 个月流水 + 余额证明建议)。
#
# ⚠️ 警告: 任何具体数字必须经业务同学核实使领馆当期要求后再更新。
# 这里的数据是 v1 估算值,实际部署前务必 review。

FINANCIAL_STANDARD_TABLE: Dict[Tuple[str, str], Dict[str, Any]] = {
    # 申根 (统一标准,源国不限)
    ("*", "SCHENGEN"): {
        "min_coverage_months": 3,
        "daily_min_eur": 65.0,           # 申根按行程天数 × EUR 45~100
        "need_balance_cert": True,
        "hard_block": True,              # 余额不足会直接被拒
    },
    # 美国 (B1/B2)
    ("*", "US"): {
        "min_coverage_months": 6,        # 6 个月流水 + 余额证明
        "recommend_balance": True,
        "hard_block": False,             # 美签看综合,余额不足不直接拒
    },
    # 日本
    ("*", "JP"): {
        "min_coverage_months": 3,
        "daily_min_jpy": 10000.0,        # 估算 ¥500/天
        "need_balance_cert": False,
        "hard_block": False,
    },
    # 韩国
    ("*", "KR"): {
        "min_coverage_months": 3,
        "need_balance_cert": False,
        "hard_block": False,
    },
    # 新加坡
    ("*", "SG"): {
        "min_coverage_months": 3,
        "need_balance_cert": False,
        "hard_block": False,
    },
    # 英国
    ("*", "GB"): {
        "min_coverage_months": 3,
        "daily_min_gbp": 70.0,
        "need_balance_cert": False,
        "hard_block": False,
    },
    # 越南 (去越南,中国护照免签,主要给其他源国用)
    ("*", "VN"): {
        "min_coverage_months": 1,        # 越南签证材料简单
        "need_balance_cert": False,
        "hard_block": False,
    },
    # 印尼
    ("*", "ID"): {
        "min_coverage_months": 1,
        "need_balance_cert": False,
        "hard_block": False,
    },
    # 泰国
    ("*", "TH"): {
        "min_coverage_months": 1,
        "need_balance_cert": False,
        "hard_block": False,
    },
}


# 源国 -> 货币
SOURCE_COUNTRY_CCY = {
    "CN": "CNY",
    "VN": "VND",
    "ID": "IDR",
    # 其他默认 USD
    "*": "USD",
}

# 目的国 -> 货币
DESTINATION_CCY = {
    "US": "USD",
    "JP": "JPY",
    "KR": "KRW",
    "SG": "SGD",
    "GB": "GBP",
    "SCHENGEN": "EUR",
    "FR": "EUR",
    "DE": "EUR",
    "VN": "VND",
    "ID": "IDR",
    "TH": "THB",
}


# ---------------------------------------------------------------- #
# 汇率表 (W54 v1: 静态表,后续接实时 API)                                #
# ---------------------------------------------------------------- #
# 数据来源: 业务同学每月手动更新,as_of 注明日期。
# 原则: 1 source_ccy = rate dest_ccy
# 例: 1 CNY = 0.128 EUR (汇率随市场波动)
#
# 2026-07-01 业务同学核实值 (示意值,部署前必须再 review):
FX_RATES_TABLE: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("CNY", "EUR"): {"rate": 0.128, "as_of": "2026-07-01", "source": "static@business"},
    ("CNY", "USD"): {"rate": 0.139, "as_of": "2026-07-01", "source": "static@business"},
    ("CNY", "JPY"): {"rate": 21.5, "as_of": "2026-07-01", "source": "static@business"},
    ("CNY", "GBP"): {"rate": 0.110, "as_of": "2026-07-01", "source": "static@business"},
    ("CNY", "KRW"): {"rate": 192.0, "as_of": "2026-07-01", "source": "static@business"},
    ("CNY", "SGD"): {"rate": 0.187, "as_of": "2026-07-01", "source": "static@business"},
    ("VND", "EUR"): {"rate": 0.0000357, "as_of": "2026-07-01", "source": "static@business"},
    ("VND", "USD"): {"rate": 0.0000388, "as_of": "2026-07-01", "source": "static@business"},
    ("IDR", "EUR"): {"rate": 0.0000563, "as_of": "2026-07-01", "source": "static@business"},
    ("IDR", "USD"): {"rate": 0.0000613, "as_of": "2026-07-01", "source": "static@business"},
}


# ---------------------------------------------------------------- #
# Dataclasses                                                         #
# ---------------------------------------------------------------- #
@dataclass
class FinancialStandard:
    """某个 (源国, 目的国) 组合的财务门槛。"""
    source_country: str
    destination: str
    min_coverage_months: int = 3
    recommend_balance: bool = False
    need_balance_cert: bool = False
    hard_block: bool = False
    # 申根的 daily_min_eur / 日本的 daily_min_jpy ...
    daily_min: Optional[float] = None
    daily_min_ccy: Optional[str] = None


@dataclass
class FxRate:
    """一对 (源币, 目的币) 的汇率。"""
    source_ccy: str
    dest_ccy: str
    rate: float
    as_of: str
    source: str


# ---------------------------------------------------------------- #
# 查询 API                                                            #
# ---------------------------------------------------------------- #
def get_financial_standard(source_country: str, destination: str) -> FinancialStandard:
    """按 (source_country, destination) 查财务标准。

    兜底: 找不到精确匹配时,试 ("*", destination);再兜底 ("*", "*") 默认 3 个月。
    """
    dest = destination.upper()
    src = source_country.upper()
    # 精确匹配 (src, dest)
    cfg = FINANCIAL_STANDARD_TABLE.get((src, dest))
    # 兜底 (*, dest)
    if cfg is None:
        cfg = FINANCIAL_STANDARD_TABLE.get(("*", dest))
    # 再兜底
    if cfg is None:
        cfg = {"min_coverage_months": 3, "need_balance_cert": False, "hard_block": False}

    # 提取 daily_min (申根 EUR, 日本 JPY, 英国 GBP ...)
    daily_min = None
    daily_min_ccy = None
    for k in ("daily_min_eur", "daily_min_jpy", "daily_min_gbp", "daily_min"):
        if k in cfg:
            daily_min = float(cfg[k])
            daily_min_ccy = k.replace("daily_min_", "").upper()
            break

    return FinancialStandard(
        source_country=src,
        destination=dest,
        min_coverage_months=int(cfg.get("min_coverage_months", 3)),
        recommend_balance=bool(cfg.get("recommend_balance", False)),
        need_balance_cert=bool(cfg.get("need_balance_cert", False)),
        hard_block=bool(cfg.get("hard_block", False)),
        daily_min=daily_min,
        daily_min_ccy=daily_min_ccy,
    )


def get_fx_rate(source_ccy: str, dest_ccy: str) -> Optional[FxRate]:
    """查 source_ccy → dest_ccy 的汇率。

    找不到返 None(让 caller 决定怎么 fallback)。
    """
    if not source_ccy or not dest_ccy:
        return None
    s = source_ccy.upper()
    d = dest_ccy.upper()
    if s == d:
        return FxRate(source_ccy=s, dest_ccy=d, rate=1.0,
                      as_of="identity", source="identity")
    cfg = FX_RATES_TABLE.get((s, d))
    if cfg is None:
        return None
    return FxRate(
        source_ccy=s,
        dest_ccy=d,
        rate=float(cfg["rate"]),
        as_of=str(cfg.get("as_of", "")),
        source=str(cfg.get("source", "unknown")),
    )


def convert_balance(
    amount: float,
    source_ccy: str,
    dest_ccy: str,
) -> Tuple[Optional[float], Optional[FxRate]]:
    """把 amount 从 source_ccy 换算到 dest_ccy。

    Returns:
        (converted_amount, fx_rate) — 找不到汇率时返 (None, None)
    """
    if amount is None:
        return None, None
    fx = get_fx_rate(source_ccy, dest_ccy)
    if fx is None:
        return None, None
    return round(amount * fx.rate, 2), fx


# ---------------------------------------------------------------- #
# 余额判定                                                            #
# ---------------------------------------------------------------- #
@dataclass
class BalanceVerdict:
    """余额是否达标的判定结果。"""
    meets_minimum: bool
    ending_balance_src: float
    ending_balance_dest: float
    daily_min_dest: Optional[float]
    recommended_balance_dest: Optional[float] = None
    detail: str = ""
    severity: str = "info"  # info|warn|block


def evaluate_balance(
    ending_balance_src: Optional[float],
    source_country: str,
    destination: str,
    *,
    stay_days: Optional[int] = None,
    daily_min_dest: Optional[float] = None,
    recommended_balance_dest: Optional[float] = None,
) -> BalanceVerdict:
    """判定余额是否达标。

    Args:
        ending_balance_src: 用户流水里的 ending_balance(源国货币)
        source_country: CN|VN|ID
        destination: US|JP|...
        stay_days: 行程天数(用于申根 daily_min 估算)
        daily_min_dest: 申根/日最低(目的国货币)— None 时走配置
        recommended_balance_dest: 建议余额(目的国货币)— None 时跳过

    Returns:
        BalanceVerdict
    """
    src_ccy = SOURCE_COUNTRY_CCY.get(source_country.upper(), "USD")
    dest_ccy = DESTINATION_CCY.get(destination.upper(), "USD")
    std = get_financial_standard(source_country, destination)

    # 选 daily_min: caller 提供优先,否则用 std
    daily = daily_min_dest if daily_min_dest is not None else std.daily_min

    if ending_balance_src is None:
        return BalanceVerdict(
            meets_minimum=False,
            ending_balance_src=0.0,
            ending_balance_dest=0.0,
            daily_min_dest=daily,
            recommended_balance_dest=recommended_balance_dest,
            detail="用户未提供 ending_balance,无法判定余额",
            severity="warn",
        )

    converted, fx = convert_balance(ending_balance_src, src_ccy, dest_ccy)
    if converted is None:
        return BalanceVerdict(
            meets_minimum=False,
            ending_balance_src=ending_balance_src,
            ending_balance_dest=0.0,
            daily_min_dest=daily,
            recommended_balance_dest=recommended_balance_dest,
            detail=f"无法从 {src_ccy} 换算到 {dest_ccy},缺汇率",
            severity="warn",
        )

    # 申根: 用 daily × stay_days 算最低
    threshold = None
    if daily is not None and stay_days is not None and stay_days > 0:
        threshold = daily * stay_days

    meets = True
    detail = ""
    severity = "info"

    if threshold is not None:
        if converted < threshold:
            meets = False
            detail = (f"余额 {converted:,.2f} {dest_ccy} 低于行程预算 "
                      f"{threshold:,.2f} {dest_ccy} ({stay_days} 天 × {daily:,.2f}/天)")
            severity = "block" if std.hard_block else "warn"
        else:
            detail = f"余额 {converted:,.2f} {dest_ccy} 满足行程预算 {threshold:,.2f} {dest_ccy}"

    if recommended_balance_dest is not None and converted < recommended_balance_dest:
        # 即使达标行程,也不到建议余额(美签常见)
        if meets:
            meets = False
            detail += f"; 但低于建议余额 {recommended_balance_dest:,.2f} {dest_ccy}"
            severity = "warn"

    return BalanceVerdict(
        meets_minimum=meets,
        ending_balance_src=ending_balance_src,
        ending_balance_dest=converted,
        daily_min_dest=threshold or daily,
        recommended_balance_dest=recommended_balance_dest,
        detail=detail,
        severity=severity,
    )