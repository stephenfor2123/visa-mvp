"""银行流水结构化解析器 (W51)

背景
----
OCR 之后从银行流水 PDF/图片里拿到的只是一坨按行识别的文本:
    [{text: "2024-03-15", bbox, confidence}, {text: "ATM 取现", ...}, ...]

签证官真正看的是「这条用户近期有没有稳定收入、流水能不能覆盖行程预算、
有没有大额异常进出」,这些信息要靠把上百条交易聚合出来。规则引擎
VisaDiagnoser 看的也是聚合后的字段,不是单条交易明细。

策略
----
V1 走 hybrid:regex 优先,LLM 兜底。
    1. OCR 全文 -> regex 解析成 transactions[] + 月度聚合。
       中国主要行 (工/农/中/建/招/交) 的电子流水有相对稳定的格式,
       9 成能命中。
    2. 若解析出 N>=10 条 -> 直接返回,不再调 LLM。
    3. 若解析出 N<10 条(或 regex 全失败) -> 拿 OCR 全文给 MiniMax
       做结构化抽取 (跟 itinerary_generator 用同一套 client)。
    4. LLM 也失败 -> fallback 到只放原始 OCR 文本,不报错,
       VisaDiagnoser 会基于"无 transactions"给出建议。

输入 / 输出
----
输入:  bytes_content (原始文件) 或 ocr_items (已 OCR 出的 [{text,bbox,confidence}])。
      优先用 ocr_items (轻量),bytes 在没 OCR 过的时候才传。
输出: {
    "transactions": [{"date": "YYYY-MM-DD", "description": "...", "amount": 1234.56,
                       "currency": "CNY", "balance": 12345.67, "direction": "in"|"out"}],
    "monthly_summary": [{"month": "2024-03", "income": 12000.0,
                          "expense": 8000.0, "net": 4000.0,
                          "ending_balance": 12500.0, "txn_count": 23}],
    "coverage_months": 6,           # 流水跨多少个月
    "txn_count": 142,
    "monthly_income_avg": 11000.0,
    "monthly_expense_avg": 7800.0,
    "ending_balance": 12500.0,
    "large_inflows": [{"date": "...", "amount": 50000.0, "description": "..."}],
    "large_outflows": [{"date": "...", "amount": 80000.0, "description": "..."}],
    "parser": "regex"|"llm"|"none",
    "confidence": 0.0..1.0,
}
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# Locale 配置 (W53 源国差异)                                          #
# ---------------------------------------------------------------- #
# 三个源国的"千分位/小数分隔符/日期格式/常见余额关键词/货币/方向词"差异,
# 集中维护在 LOCALE_TABLE 里,parser 按 locale 走对应规则。
# 这是设计上最大的变更点:之前 parser 写死 CNY + 中式日期 + 中式金额。
#
# 千分位/小数规则:
#   CN: 1,234.56  -> 逗号千分位 + 点小数
#   VN: 1.234.567 -> 点千分位 (无小数常见;若有: 1.234.567,89 逗号小数)
#   ID: 1.234.567 -> 点千分位 (若有小数: 1.234.567,89)
#
# 日期格式 (越/印尼常用 DD/MM/YYYY 或 DD-MM-YY):
#   CN: YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD
#   VN: DD/MM/YYYY / DD-MM-YYYY / DD/MM/YY
#   ID: DD/MM/YYYY / DD-MM-YY
#
# 余额关键词 (OCR 出的字段名千奇百怪,这里识别 header 行):
#   CN: 余额 / 账户余额 / 余额(元)
#   VN: Số dư / So du / SỐ DƯ
#   ID: Saldo / Saldo Akhir
#
# 方向词 (描述里的 income/out 判定):
#   CN: 收入/存入/转入/汇入/工资/退款
#   VN: Nhận / Ghi có / Lương / Chuyển đến / Hoàn tiền
#   ID: Terima / Kredit / Gaji / Setor / Pengembalian
#   (支出方向只要是负数或没匹配到关键词,默认 out)
LOCALE_TABLE: Dict[str, Dict[str, Any]] = {
    "CN": {
        "currency": "CNY",
        "thousands_sep": ",",
        "decimal_sep": ".",
        "date_patterns": [
            r"(?P<y>20\d{2})[-/.](?P<m>0?[1-9]|1[0-2])[-/.](?P<d>(?:[12]\d|3[01]|0\d)|0?[1-9])",
            r"(?P<y2>20\d{2})(?P<m2>0[1-9]|1[0-2])(?P<d2>(?:[12]\d|3[01]|0\d)|0?[1-9])",
        ],
        # order=False -> 日期是 (Y,M,D);order="dmy" -> (D,M,Y)
        "date_order": False,
        "balance_keys": ["余额", "账户余额", "余额(元)", "余额（元）", "余额（元）"],
        "income_keys": ["收入", "存入", "转入", "汇入", "工资", "退款", "收到"],
        "expense_keys": ["支出", "转出", "ATM", "消费", "扫码", "扣款", "取现", "支付"],
        "large_threshold": 50000.0,
    },
    "VN": {
        "currency": "VND",
        "thousands_sep": ".",
        "decimal_sep": ",",
        "date_patterns": [
            # DD/MM/YYYY 或 DD-MM-YYYY (D/M 单数字都允许)
            r"(?P<d>0?[1-9]|[12]\d|3[01])[-/](?P<m>0?[1-9]|1[0-2])[-/](?P<y>20\d{2})",
            # DD/MM/YY (2 位年)
            r"(?P<d>0?[1-9]|[12]\d|3[01])[-/](?P<m>0?[1-9]|1[0-2])[-/](?P<y_short>\d{2})",
        ],
        "date_order": "dmy",
        "balance_keys": ["Số dư", "So du", "SỐ DƯ", "số dư", "Balance"],
        "income_keys": ["Nhận", "Ghi có", "Lương", "Chuyển đến", "Hoàn tiền", "Thu nhập"],
        "expense_keys": ["Chuyển đi", "Ghi nợ", "Rút", "Thanh toán", "Mua", "Phí"],
        # 越南工资可能数千万越南盾,5 万 VND 不算大;阈值用 50,000,000 VND ≈ ¥14000
        "large_threshold": 50_000_000.0,
    },
    "ID": {
        "currency": "IDR",
        "thousands_sep": ".",
        "decimal_sep": ",",
        "date_patterns": [
            r"(?P<d>0?[1-9]|[12]\d|3[01])[-/](?P<m>0?[1-9]|1[0-2])[-/](?P<y>20\d{2})",
            r"(?P<d>0?[1-9]|[12]\d|3[01])[-/](?P<m>0?[1-9]|1[0-2])[-/](?P<y_short>\d{2})",
        ],
        "date_order": "dmy",
        "balance_keys": ["Saldo", "Saldo Akhir", "Balance", "Sisa saldo"],
        "income_keys": ["Terima", "Kredit", "Gaji", "Setor", "Pengembalian", "Pemasukan"],
        "expense_keys": ["Kirim", "Debet", "Tarik", "Bayar", "Beli", "Biaya"],
        # 印尼盾同样大数字,5000 万 IDR ≈ ¥22000
        "large_threshold": 50_000_000.0,
    },
}


def get_locale(source_country: str) -> Dict[str, Any]:
    """按 source_country 返回 locale 配置;未知国家 fallback 到 CN。"""
    if not source_country:
        return LOCALE_TABLE["CN"]
    cc = source_country.upper()
    if cc in LOCALE_TABLE:
        return LOCALE_TABLE[cc]
    _log.warning("Unknown source_country %r, fallback to CN locale", source_country)
    return LOCALE_TABLE["CN"]


# 兼容旧代码直接 import 的常量(下面会逐步替换,先保留 + 标 deprecated)
_DATE_PATTERNS = LOCALE_TABLE["CN"]["date_patterns"]

# 金额:任意位整数 + 可选千分位逗号 + 可选 1-2 位小数 + 可选正负号
# 关键:整数部分不能限定 \d{1,3} 限制(那样碰到 12000 会失败,只能匹配到 120)
_AMOUNT_RE = r"[-+]?\d{1,3}(?:[,.]\d{3})+(?:\.\d{1,2})?|[-+]?\d+(?:[.,]\d{1,2})?"
# 余额:同上
_BALANCE_RE = _AMOUNT_RE

# V1 阈值 — 后端硬编码,后续挪 settings.yaml
MIN_TRANSACTIONS_FOR_REGEX_OK = 10
# W53: 大额阈值不再硬编码 CNY,改走 locale["large_threshold"]
# 保留 LARGE_TRANSACTION_THRESHOLD_CNY 仅供测试和老代码兼容
LARGE_TRANSACTION_THRESHOLD_CNY = 50000.0
MIN_STATEMENT_MONTHS_RECOMMENDED = 3  # 流水 <3 个月签证官会问


# ---------------------------------------------------------------- #
# OCR items → 全文                                                   #
# ---------------------------------------------------------------- #
def ocr_items_to_text(items: Iterable[Dict[str, Any]]) -> str:
    """把 OCR items 按 y 坐标(行)重排,再按 x 顺序拼接每个 row 内的 word。

    PaddleOCR / Tesseract 给的 items 默认乱序 (PaddleOCR 是图遍历顺序),
    同一行的词必须按 x 排好,正则才能跨字段匹配。

    算法: greedy 行聚类 — 先把所有 items 按 y-center 排序,然后用一个动态
    阈值(`行高 × 0.6`)判断新 item 是否属于当前行,换行时开新 row。比固定
    `round(y/10)` 更稳健(行间距 <10px 时不会误合并,>30px 时不会误拆)。
    """
    if not items:
        return ""

    # 取每个 item 的 y center + x left + text
    placed: List[Tuple[float, float, str]] = []
    for it in items:
        bbox = it.get("bbox") or []
        if len(bbox) < 4:
            continue
        ys = [float(p[1]) for p in bbox[:4]]
        xs = [float(p[0]) for p in bbox[:4]]
        text = (it.get("text") or "").strip()
        if not text:
            continue
        y_center = sum(ys) / len(ys)
        # 估算本行行高(bbox height 平均)
        height = max(ys) - min(ys) or 20.0
        x_left = min(xs)
        placed.append((y_center, x_left, text, height))

    if not placed:
        return ""

    # 按 y center 排序
    placed.sort(key=lambda t: (t[0], t[1]))

    rows: List[List[Tuple[float, str]]] = []
    current_y = placed[0][0]
    current_height = placed[0][3]
    current_row: List[Tuple[float, str]] = []
    for y_center, x_left, text, height in placed:
        # 同行阈值: 当前行高度 × 0.6
        threshold = max(current_height, height) * 0.6
        if abs(y_center - current_y) > threshold:
            # 开新行
            rows.append(sorted(current_row, key=lambda w: w[0]))
            current_row = []
            current_y = y_center
            current_height = height
        current_row.append((x_left, text))
        # rolling average y center,这样下一行能跟着调
        current_y = 0.7 * current_y + 0.3 * y_center
    if current_row:
        rows.append(sorted(current_row, key=lambda w: w[0]))

    lines = [" ".join(w[1] for w in row) for row in rows]
    return "\n".join(lines)


# ---------------------------------------------------------------- #
# Regex 解析                                                          #
# ---------------------------------------------------------------- #
# W53: 按 locale 动态编译 _LINE_RE。
# 之前是写死 (Y,M,D) 中文格式,现在 CN 走 (Y,M,D),VN/ID 走 (D,M,Y)。
# 描述允许任何 unicode (中/越/印尼/英),贪婪匹配到金额前。
def _compile_line_re(locale: Dict[str, Any]) -> re.Pattern:
    """按 locale 编译交易行正则。

    W56: 接受 locale 主顺序 + 全部 fallback 顺序(ymd/dmy 都试),
    因为中文口语写日期也常用 "01/03/2024" (dmy)。
    """
    # 主顺序按 locale
    primary = _date_alt_for_locale(locale)
    # fallback: 另一种顺序也接受(避免漏掉混用格式)
    if locale.get("date_order") == "dmy":
        fallback = _date_alt_for_ymd()
    else:
        fallback = _date_alt_for_dmy()
    # 主+fallback 都接受
    date_alt = f"(?:{primary}|{fallback})"

    pat = (
        rf"^"
        rf"(?:{date_alt})"            # 日期(主或 fallback)
        rf"\s+(?P<desc>.+?)\s+"       # 描述(非贪婪)
        rf"(?P<amount>{_AMOUNT_RE})"  # 金额
        rf"(?:\s+(?P<balance>{_BALANCE_RE}))?"  # 可选余额
        rf"\s*$"
    )
    return re.compile(pat)


def _date_alt_for_locale(locale: Dict[str, Any]) -> str:
    """按 locale 编译日期 alternation。"""
    if locale.get("date_order") == "dmy":
        return _date_alt_for_dmy()
    return _date_alt_for_ymd()


def _date_alt_for_ymd() -> str:
    """YYYY-MM-DD / YYYY/MM/DD / YYYYMMDD。"""
    return (
        r"(?:(?P<date_a>20\d{2})[-/.](?P<date_m>0?[1-9]|1[0-2])[-/.](?P<date_d>0?[1-9]|[12]\d|3[01])"
        r"|(?P<date2>20\d{2})(?P<date2_m>0[1-9]|1[0-2])(?P<date2_d>0[1-9]|[12]\d|3[01]))"
    )


def _date_alt_for_dmy() -> str:
    """DD/MM/YYYY / DD-MM-YYYY / DD/MM/YY。"""
    return (
        r"(?:(?P<d>0?[1-9]|[12]\d|3[01])[-/](?P<m>0?[1-9]|1[0-2])[-/](?P<y>20\d{2})"
        r"|(?P<d_s>0?[1-9]|[12]\d|3[01])[-/](?P<m_s>0?[1-9]|1[0-2])[-/](?P<y_s>\d{2}))"
    )


# 保留旧名以兼容 import 的代码(老代码传 ocr_text 不带 locale 会走 CN 默认)
_DATE_REGEX_COMPILED = [re.compile(p) for p in LOCALE_TABLE["CN"]["date_patterns"]]
_LINE_RE_DEFAULT = _compile_line_re(LOCALE_TABLE["CN"])


def _parse_amount(raw: str, locale: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """解析金额数字。

    W53: 之前 hardcode 中式(逗号当千分位剥掉),会把越南/印尼
    "1.234.567,89" 错成 1.234567(实为 1234567.89,差 100 倍)。
    现在按 locale["thousands_sep"] / ["decimal_sep"] 走。

    关键规则:
      - thousands_sep 是真正"千分位": 出现 N 次都剥掉(整数部分)
      - decimal_sep 是真正"小数点": 只能出现 1 次,在最后
      - 数字串里出现的"另一种分隔符"(在 CN locale 里看到 . 以外的,或
        在 VN locale 里看到 , 以外的) → 视为非法格式,返回 None
        而不是猜。

    Args:
        raw: 原始字符串 (可以带 ± / 千分位 / 小数 / 空格)
        locale: get_locale() 返回的 dict;None 时走 CN 默认
    """
    if not raw:
        return None
    if locale is None:
        locale = LOCALE_TABLE["CN"]
    thou = locale.get("thousands_sep", ",")
    dec = locale.get("decimal_sep", ".")

    s = str(raw).strip()
    # 1) 处理符号
    sign = 1
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("-"):
        sign = -1
        s = s[1:]
    # 2) 剥空白
    s = s.replace(" ", "").replace("\u00a0", "").replace("\u3000", "")

    # 3) 验证: 只允许 [0-9 thou dec]
    allowed = set("0123456789") | {thou, dec}
    if any(c not in allowed for c in s):
        return None

    # 4) 剥千分位
    s = s.replace(thou, "")

    # 5) 小数点统一成 .
    if dec != ".":
        s = s.replace(dec, ".")

    # 6) 验证: 现在只能是 [0-9.]+
    if not s or s.count(".") > 1:
        return None
    if "." in s and s.endswith("."):
        s = s[:-1]  # 末尾孤立的 . 当成整数

    try:
        return sign * float(s)
    except ValueError:
        return None


def _parse_date(raw: str, locale: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """统一返回 ISO YYYY-MM-DD,失败 None。

    W53: 输入可以是:
      - ISO 串 ("2024-03-15") — caller 拼好的,直接用
      - locale 原始串 ("15/03/2024" for VN) — 按 locale patterns 解析
      - 其他顺序 (e.g. CN 用户偶尔写 "01/03/2024" dmy) — fallback 试全部 locale

    Args:
        raw: 日期字符串
        locale: get_locale() 配置;CN 默认
    """
    if not raw:
        return None
    raw = raw.strip()
    if locale is None:
        locale = LOCALE_TABLE["CN"]

    # 快路径: 已经是 ISO 格式 (YYYY-MM-DD 或 YYYY/MM/DD 或 YYYYMMDD)
    iso_match = re.match(r"^(\d{4})[-/]?(\d{2})[-/]?(\d{2})$", raw)
    if iso_match and raw[:4].isdigit() and int(raw[:4]) >= 1900:
        y, mo, d = iso_match.groups()
        try:
            return date(int(y), int(mo), int(d)).isoformat()
        except (ValueError, TypeError):
            pass

    # 主路径: 按 locale date_patterns
    patterns = locale.get("date_patterns") or _DATE_PATTERNS
    result = _try_date_patterns(raw, patterns, locale)
    if result:
        return result

    # Fallback (W56): locale 不匹配时,试其他 locale 的 patterns
    # 例: CN 用户写 "01/03/2024" 实为 dmy — 试 VN/ID 的 dmy patterns
    for cc, fallback_loc in LOCALE_TABLE.items():
        if fallback_loc is locale:
            continue
        fb_patterns = fallback_loc.get("date_patterns") or []
        if not fb_patterns:
            continue
        result = _try_date_patterns(raw, fb_patterns, fallback_loc)
        if result:
            return result

    return None


def _try_date_patterns(raw: str, patterns: List[str], locale: Dict[str, Any]) -> Optional[str]:
    """内部 helper: 给定 patterns 和 locale 试解析 raw。"""
    order = locale.get("date_order", False)
    for pat in patterns:
        m = re.match(rf"^{pat}$", raw)
        if not m:
            continue
        gd = m.groupdict()
        if order == "dmy":
            d = gd.get("d") or gd.get("d_s")
            mo = gd.get("m") or gd.get("m_s")
            y = gd.get("y") or gd.get("y_short")
            if y and len(y) == 2:
                y = "20" + y
        else:
            d = gd.get("d") or gd.get("d2") or gd.get("date_d") or gd.get("date2_d")
            mo = gd.get("m") or gd.get("m2") or gd.get("date_m") or gd.get("date2_m")
            y = gd.get("y") or gd.get("y2") or gd.get("date_a") or gd.get("date2")
        if not (y and mo and d):
            continue
        try:
            return date(int(y), int(mo), int(d)).isoformat()
        except (ValueError, TypeError):
            continue
    return None


def parse_with_regex(ocr_text: str, source_country: str = "CN") -> List[Dict[str, Any]]:
    """从 OCR 全文抽取交易明细。返回 transactions[]。

    一个行一条交易:日期 + 描述 + 金额(+ 可选余额)。
    描述里可能含 income/expense 关键词,作为 direction 推断(按 locale 走)。

    Args:
        ocr_text: OCR 全文(已按行排好)
        source_country: CN|VN|ID,决定千分位/日期格式/方向词/币种
    """
    if not ocr_text:
        return []
    locale = get_locale(source_country)
    line_re = _compile_line_re(locale)
    out: List[Dict[str, Any]] = []
    for line in ocr_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = line_re.match(line)
        if not m:
            continue
        gd = m.groupdict()
        # 按 locale date_order 重组日期串喂给 _parse_date
        order = locale.get("date_order", False)
        if order == "dmy":
            d_raw = gd.get("d") or gd.get("d_s")
            m_raw = gd.get("m") or gd.get("m_s")
            y_raw = gd.get("y") or ("20" + gd["y_s"] if gd.get("y_s") else None)
        else:
            if gd.get("date_a"):
                d_raw, m_raw, y_raw = gd["date_d"], gd["date_m"], gd["date_a"]
            elif gd.get("date2"):
                d_raw, m_raw, y_raw = gd["date2_d"], gd["date2_m"], gd["date2"]
            else:
                # Fallback 用了 dmy — 也可能 match 上
                d_raw = gd.get("d") or gd.get("d_s")
                m_raw = gd.get("m") or gd.get("m_s")
                y_raw = gd.get("y") or ("20" + gd["y_s"] if gd.get("y_s") else None)
        if not (d_raw and m_raw and y_raw):
            continue
        date_raw = f"{int(y_raw):04d}-{int(m_raw):02d}-{int(d_raw):02d}"
        d = _parse_date(date_raw, locale)
        amount = _parse_amount(gd.get("amount", ""), locale)
        balance = _parse_amount(gd.get("balance", ""), locale)
        if not d or amount is None:
            continue
        desc = (gd.get("desc") or "").strip()
        direction = _infer_direction(desc, locale)
        if amount < 0:
            amount = abs(amount)
        out.append({
            "date": d,
            "description": desc,
            "amount": amount,
            "balance": balance,
            "direction": direction,
            "currency": locale["currency"],
        })
    return out


def _infer_direction(desc: str, locale: Dict[str, Any]) -> Optional[str]:
    """按 locale 关键词推断 income/expense。

    关键词都做 case-insensitive 比对(越语带声调符,大小写不敏感即可)。
    """
    if not desc:
        return None
    desc_l = desc.lower()
    income_keys = [k.lower() for k in locale.get("income_keys", [])]
    expense_keys = [k.lower() for k in locale.get("expense_keys", [])]
    if any(k in desc_l for k in income_keys):
        return "in"
    if any(k in desc_l for k in expense_keys):
        return "out"
    return None


# ---------------------------------------------------------------- #
# 月度聚合 + 大额进出                                                  #
# ---------------------------------------------------------------- #
def aggregate(transactions: List[Dict[str, Any]], source_country: str = "CN") -> Dict[str, Any]:
    """从 transactions 计算 monthly_summary + large_inflows/large_outflows。

    Args:
        transactions: parse_with_regex 出的 [{date, amount, balance, direction, currency}, ...]
        source_country: 大额阈值走 locale["large_threshold"]
    """
    if not transactions:
        return {
            "monthly_summary": [],
            "coverage_months": 0,
            "txn_count": 0,
            "monthly_income_avg": None,
            "monthly_expense_avg": None,
            "ending_balance": None,
            "large_inflows": [],
            "large_outflows": [],
        }

    months: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "income": 0.0, "expense": 0.0, "net": 0.0, "txn_count": 0,
        "ending_balance": None,
    })
    large_inflows: List[Dict[str, Any]] = []
    large_outflows: List[Dict[str, Any]] = []
    locale = get_locale(source_country)
    large_threshold = float(locale.get("large_threshold", LARGE_TRANSACTION_THRESHOLD_CNY))

    # 同一日多笔的话 balance 取最后一个
    last_balance_by_month: Dict[str, Optional[float]] = {}

    for t in transactions:
        d = t.get("date") or ""
        if not d or len(d) < 7:
            continue
        month = d[:7]
        amount = float(t.get("amount") or 0)
        balance = t.get("balance")
        direction = t.get("direction")

        if direction == "in":
            months[month]["income"] += amount
        elif direction == "out":
            months[month]["expense"] += amount
        else:
            # unknown direction — 视为支出但加入 weighted_avg
            months[month]["expense"] += amount

        months[month]["net"] = months[month]["income"] - months[month]["expense"]
        months[month]["txn_count"] += 1

        if balance is not None:
            months[month]["ending_balance"] = balance
            last_balance_by_month[month] = balance

        if amount >= large_threshold:
            (large_inflows if direction == "in" else large_outflows).append({
                "date": d,
                "amount": amount,
                "description": t.get("description", ""),
            })

    summary_list = []
    for month_key in sorted(months.keys()):
        s = months[month_key]
        summary_list.append({
            "month": month_key,
            "income": round(s["income"], 2),
            "expense": round(s["expense"], 2),
            "net": round(s["net"], 2),
            "txn_count": s["txn_count"],
            "ending_balance": s["ending_balance"],
        })

    income_months = [m for m in summary_list if m["income"] > 0]
    expense_months = [m for m in summary_list if m["expense"] > 0]

    coverage_months = len(summary_list)
    ending_balance = None
    if summary_list:
        # 取最后一个月(最新)的余额
        ending_balance = summary_list[-1]["ending_balance"]

    return {
        "monthly_summary": summary_list,
        "coverage_months": coverage_months,
        "txn_count": len(transactions),
        "monthly_income_avg": (
            round(sum(m["income"] for m in income_months) / len(income_months), 2)
            if income_months else None
        ),
        "monthly_expense_avg": (
            round(sum(m["expense"] for m in expense_months) / len(expense_months), 2)
            if expense_months else None
        ),
        "ending_balance": ending_balance,
        "large_inflows": large_inflows,
        "large_outflows": large_outflows,
    }


# ---------------------------------------------------------------- #
# 工资断档检测 (W52)                                                  #
# ---------------------------------------------------------------- #
# 阈值:连续 ≥1 个月没收到任何"工资/收入/汇入/退款"类入账,
# 提示用户解释资金来源。这里用"任意有 income 的月份"作为分母基准,
# 然后找相邻 income 月份之间的空白月份。
def detect_income_gaps(monthly_summary: List[Dict[str, Any]],
                       min_income: float = 100.0) -> List[Dict[str, Any]]:
    """从 monthly_summary 找连续无 income 的月份(每段 gap 都返回)。

    Args:
        monthly_summary: aggregate 出的 [{month, income, ...}, ...]
        min_income: 视为"有收入"的最低金额(避免 5 块退款被算作 income)

    Returns:
        [{start_month: "2024-08", end_month: "2024-09", gap_months: 2}, ...]
    """
    if not monthly_summary:
        return []

    # 连续月份标记
    months = [m["month"] for m in monthly_summary]
    income_positive = [m["income"] >= min_income for m in monthly_summary]

    # 找所有 income=False 的连续段
    gaps: List[Dict[str, Any]] = []
    cur_start = None
    cur_end = None
    for i, m in enumerate(months):
        if not income_positive[i]:
            if cur_start is None:
                cur_start = m
            cur_end = m
        else:
            # 当前月有收入,如果之前有 gap 段,结算它
            if cur_start is not None and cur_end is not None:
                gap_count = _months_between(cur_start, cur_end)
                if gap_count >= 1:
                    gaps.append({
                        "start_month": cur_start,
                        "end_month": cur_end,
                        "gap_months": gap_count,
                    })
                cur_start = None
                cur_end = None
    # 末尾 gap 段
    if cur_start is not None and cur_end is not None:
        gap_count = _months_between(cur_start, cur_end)
        if gap_count >= 1:
            gaps.append({
                "start_month": cur_start,
                "end_month": cur_end,
                "gap_months": gap_count,
            })
    return gaps


def _months_between(start_month: str, end_month: str) -> int:
    """两个 YYYY-MM 串包含两端算几个月。同月返 1(因为"该月本身就是 1 个月断档")。"""
    try:
        sy, sm = int(start_month[:4]), int(start_month[5:7])
        ey, em = int(end_month[:4]), int(end_month[5:7])
        # 包含两端: 7→9 算 3 个月(7/8/9 都没收入)
        return (ey - sy) * 12 + (em - sm) + 1
    except (ValueError, IndexError):
        return 0


# ---------------------------------------------------------------- #
# LLM 兜底                                                            #
# ---------------------------------------------------------------- #
_LLM_SYSTEM_PROMPT_CN = """You are a Chinese bank-statement parser. Given OCR text from a bank statement, extract all transactions as a JSON object.

Output format (JSON object, not array):
{
  "transactions": [
    {"date": "YYYY-MM-DD", "description": "<string>", "amount": <number>, "direction": "in"|"out", "balance": <number|null>}
  ]
}

Rules:
- amount is a positive number (use direction field for sign).
- direction: "in" for income/deposit/transfer-in/salary/refund, "out" for expense/withdraw/transfer-out/payment/consumption.
- balance is optional (only when clearly present in same row).
- OCR text may contain headers, footers, summaries — skip those, only return actual transaction rows.
- If OCR text is too noisy to parse, return {"transactions": []}.
- Respond with ONLY the JSON object — no markdown fences, no commentary."""

_LLM_SYSTEM_PROMPT_VN = """Bạn là trình phân tích cú pháp sao kê ngân hàng Việt Nam. Cho văn bản OCR từ sao kê ngân hàng, hãy trích xuất tất cả giao dịch dưới dạng đối tượng JSON.

Định dạng đầu ra (đối tượng JSON, không phải mảng):
{
  "transactions": [
    {"date": "YYYY-MM-DD", "description": "<string>", "amount": <number>, "direction": "in"|"out", "balance": <number|null>}
  ]
}

Quy tắc:
- amount là số dương (dùng trường direction để biểu thị dấu).
- direction: "in" cho thu nhập/nhận tiền/chuyển đến/lương/hoàn tiền; "out" cho chi tiêu/rút tiền/chuyển đi/thanh toán/mua sắm.
- balance là tùy chọn (chỉ khi có rõ ràng trong cùng hàng).
- Số tiền có thể có dấu chấm làm phân cách hàng nghìn (ví dụ: 1.234.567) - hãy giữ nguyên giá trị số thực.
- Ngày: chuyển sang YYYY-MM-DD (DD/MM/YYYY trong gốc).
- Nếu văn bản OCR quá nhiễu, trả về {"transactions": []}.
- Chỉ trả lời bằng đối tượng JSON — không có markdown, không nhận xét."""

_LLM_SYSTEM_PROMPT_ID = """Anda adalah parser rekening koran bank Indonesia. Dari teks OCR rekening koran, ekstrak semua transaksi sebagai objek JSON.

Format output (objek JSON, bukan array):
{
  "transactions": [
    {"date": "YYYY-MM-DD", "description": "<string>", "amount": <number>, "direction": "in"|"out", "balance": <number|null>}
  ]
}

Aturan:
- amount adalah angka positif (gunakan field direction untuk tanda).
- direction: "in" untuk pemasukan/terima/kredit/gaji/setor/pengembalian; "out" untuk pengeluaran/kirim/debet/tarik/bayar.
- balance opsional (hanya jika ada jelas di baris yang sama).
- Angka dapat menggunakan titik sebagai pemisah ribuan (misal: 1.234.567) - pertahankan nilai numerik sebenarnya.
- Tanggal: konversi ke YYYY-MM-DD (DD/MM/YYYY di sumber).
- Jika teks OCR terlalu berisik, kembalikan {"transactions": []}.
- Jawab HANYA dengan objek JSON — tanpa markdown, tanpa komentar."""

_LLM_SYSTEM_PROMPTS = {
    "CN": _LLM_SYSTEM_PROMPT_CN,
    "VN": _LLM_SYSTEM_PROMPT_VN,
    "ID": _LLM_SYSTEM_PROMPT_ID,
}

_LLM_USER_PROMPT_TMPL = "OCR text of the bank statement:\n\n{ocr_text}\n\nReturn the JSON object now."


async def _parse_with_llm(ocr_text: str, source_country: str = "CN") -> List[Dict[str, Any]]:
    """用 MiniMax 从 OCR 文本里抽 transactions。失败/未配置 -> []。

    Args:
        ocr_text: OCR 全文
        source_country: 决定走 CN/VN/ID prompt
    """
    try:
        from app.services.llm.minimax_client import get_minimax_client, MiniMaxError
    except ImportError:
        _log.warning("MiniMax client not available; skip LLM fallback")
        return []

    try:
        client = get_minimax_client()
    except Exception as exc:
        _log.info("MiniMax client not configured (%s); skip LLM fallback", exc)
        return []

    locale = get_locale(source_country)
    system_prompt = _LLM_SYSTEM_PROMPTS.get(source_country.upper(), _LLM_SYSTEM_PROMPT_CN)

    # 截断:LLM 上下文有限,银行流水可能上百行,裁到 8k 字符足够(头尾通常最值钱的)
    truncated = ocr_text[:8000]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _LLM_USER_PROMPT_TMPL.format(ocr_text=truncated)},
    ]
    try:
        content = await client.chat(messages, temperature=0.1)
    except (MiniMaxError, Exception) as exc:
        _log.warning("MiniMax chat failed for bank statement: %s", exc)
        return []

    cleaned = content.strip()
    # 兼容被包在 ```json 里
    fence = re.match(r"^```(?:json)?\s*(\{[\s\S]*?\})\s*```$", cleaned)
    if fence:
        cleaned = fence.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        _log.warning("MiniMax returned non-JSON for bank statement: %r", cleaned[:200])
        return []
    try:
        obj = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as exc:
        _log.warning("MiniMax JSON parse failed: %s", exc)
        return []
    txns = obj.get("transactions") or []
    # 校验 + 归一化
    out: List[Dict[str, Any]] = []
    for t in txns:
        if not isinstance(t, dict):
            continue
        d = t.get("date")
        amount = _parse_amount(str(t.get("amount", "")), locale)
        direction = t.get("direction")
        if not d or amount is None or direction not in ("in", "out"):
            continue
        out.append({
            "date": d,
            "description": str(t.get("description") or "").strip(),
            "amount": amount,
            "balance": _parse_amount(str(t.get("balance", "")), locale) if t.get("balance") is not None else None,
            "direction": direction,
            "currency": locale["currency"],
        })
    return out


def _parse_with_llm_sync(ocr_text: str, source_country: str = "CN", *args, **kwargs) -> List[Dict[str, Any]]:
    """同步包装 — 因为 VisaDiagnoser 是同步路径。

    接受 *args/**kwargs 是为了兼容单测里的 monkeypatch
    `lambda _ocr_text: []` —— 老测试 fixture 只 mock 1 个位置参数。
    """
    try:
        return asyncio.run(_parse_with_llm(ocr_text, source_country))
    except RuntimeError:
        # 已经在 event loop 里 (FastAPI async path),用 thread pool 跑
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, _parse_with_llm(ocr_text, source_country)).result()
    except Exception as exc:
        _log.warning("LLM fallback failed: %s", exc)
        return []


# ---------------------------------------------------------------- #
# 主入口                                                             #
# ---------------------------------------------------------------- #
def parse_bank_statement(
    ocr_items: Optional[Iterable[Dict[str, Any]]] = None,
    ocr_text: Optional[str] = None,
    source_country: str = "CN",
) -> Dict[str, Any]:
    """主入口。传 ocr_items (OCR 引擎输出) 或 ocr_text (已知全文)。

    Args:
        ocr_items / ocr_text: 输入
        source_country: CN|VN|ID — 决定千分位/日期/方向词/币种

    Returns: 见模块 docstring 的输出 schema. parser 字段标记走过哪条路。
    """
    if ocr_text is None and ocr_items is not None:
        ocr_text = ocr_items_to_text(ocr_items or [])

    ocr_text = (ocr_text or "").strip()

    # 1) regex 先试 (走 locale)
    transactions = parse_with_regex(ocr_text, source_country=source_country)
    parser_used = "regex"
    confidence = 0.8 if len(transactions) >= MIN_TRANSACTIONS_FOR_REGEX_OK else 0.4

    # 2) 不够 10 条走 LLM (本机同步包装,按 locale 走 prompt)
    if len(transactions) < MIN_TRANSACTIONS_FOR_REGEX_OK and ocr_text:
        llm_txns = _parse_with_llm_sync(ocr_text, source_country)
        # LLM 给的更多就采纳,否则保留 regex 结果
        if len(llm_txns) > len(transactions):
            transactions = llm_txns
            parser_used = "llm"
            confidence = 0.85 if len(llm_txns) >= MIN_TRANSACTIONS_FOR_REGEX_OK else 0.5

    # 3) 也都拿到了个空 -> mark "none"
    if not transactions:
        parser_used = "none"
        confidence = 0.0

    agg = aggregate(transactions, source_country=source_country)
    agg["transactions"] = transactions
    agg["parser"] = parser_used
    agg["confidence"] = confidence
    # W52: 工资断档检测 — 找连续无 income 月份,返回 [{start_month, end_month, gap_months}]
    agg["income_gaps"] = detect_income_gaps(agg.get("monthly_summary") or [])
    return agg


# ---------------------------------------------------------------- #
# W63+ 非阻断性审核提示 (Review rules)                                 #
# ---------------------------------------------------------------- #
# 上传完银行流水后给用户看的"非阻断"提示 — 不阻止用户继续办签证,只是
# 让他/她在送签前补强材料 / 准备解释。规则只产出 hint,严重度 1=info /
# 2=warning / 3=critical,前端根据 severity 选 is-info/is-warning/is-error
# 样式 (跟图 2 黄框一致)。前端 i18n 模板有 placeholder,后端只给数字 /
# 字段名,文案在前端 i18n 里写,这样多语言不用每个 locale 走 LLM。
#
# 入参:
#   parsed:        parse_bank_statement 出的完整 agg (含 monthly_summary/
#                  income_gaps/ending_balance/large_inflows 等)
#   destination:   签证目的国 ISO code (e.g. "US" / "GB"),用来挑建议余额
#                  阈值 (US$7,000 vs £5,500 等);跟 source_country (用户本国)
#                  不一样。
# 返回:
#   {
#     "rules": [
#       {code, severity, field, value, expected, suggestion_i18n_key,
#        suggestion_params}, ...
#     ],
#     "summary": {balance_ok, coverage_ok, ...}
#   }

# 跟 refresh.py / UploadItemCard.vue 的 _BANK_BALANCE_BY_COUNTRY 表对齐
# (单位:当地币种)。这里用纯数字 (不带符号),前端 i18n 加货币符号。
_RECOMMENDED_BALANCE = {
    "US": 7000, "CA": 10000, "AU": 10000, "NZ": 10000, "SG": 10000,
    "GB": 5500,
    # 申根 26 国共用 6,500 欧
    "AT": 6500, "BE": 6500, "HR": 6500, "CZ": 6500, "DK": 6500, "EE": 6500,
    "FI": 6500, "FR": 6500, "DE": 6500, "GR": 6500, "HU": 6500, "IS": 6500,
    "IT": 6500, "LV": 6500, "LI": 6500, "LT": 6500, "LU": 6500, "MT": 6500,
    "NL": 6500, "NO": 6500, "PL": 6500, "PT": 6500, "SK": 6500, "SI": 6500,
    "ES": 6500, "SE": 6500, "CH": 6500,
    "JP": 1_000_000,
    "KR": 10_000_000,
    "TH": 200_000,
    "VN": 150_000_000,
    "ID": 100_000_000,
    "IN": 500_000,
}

# 目的国币种符号 (前端再拼)
_DEST_CURRENCY = {
    "US": "USD", "CA": "CAD", "AU": "AUD", "NZ": "NZD", "SG": "SGD",
    "GB": "GBP",
    "AT": "EUR", "BE": "EUR", "HR": "EUR", "CZ": "EUR", "DK": "EUR",
    "EE": "EUR", "FI": "EUR", "FR": "EUR", "DE": "EUR", "GR": "EUR",
    "HU": "EUR", "IS": "EUR", "IT": "EUR", "LV": "EUR", "LI": "EUR",
    "LT": "EUR", "LU": "EUR", "MT": "EUR", "NL": "EUR", "NO": "EUR",
    "PL": "EUR", "PT": "EUR", "SK": "EUR", "SI": "EUR", "ES": "EUR",
    "SE": "EUR", "CH": "CHF",
    "JP": "JPY", "KR": "KRW", "TH": "THB", "VN": "VND", "ID": "IDR",
    "IN": "INR",
}


def review_rules(
    parsed: Dict[str, Any],
    destination: Optional[str] = None,
) -> Dict[str, Any]:
    """根据 parsed 解析结果产出非阻断性提示规则。

    Args:
        parsed: parse_bank_statement() 的返回 — 含 monthly_summary /
                ending_balance / coverage_months / income_gaps / large_inflows 等。
        destination: 签证目的国 ISO code。None 时跳过余额阈值检查。

    Returns:
        {
          "rules": [
            {code, severity, value, expected, suggestion_i18n_key, suggestion_params}, ...
          ],
          "summary": {
            "balance_ok": bool,
            "coverage_ok": bool,
            "income_gap_count": int,
            "large_txn_count": int,
            "parse_ok": bool,
          }
        }
    """
    rules: List[Dict[str, Any]] = []
    parser = parsed.get("parser")
    coverage = int(parsed.get("coverage_months") or 0)
    ending = parsed.get("ending_balance")
    income_gaps = parsed.get("income_gaps") or []
    large_in = parsed.get("large_inflows") or []
    large_out = parsed.get("large_outflows") or []
    monthly_income_avg = parsed.get("monthly_income_avg")
    txn_count = int(parsed.get("txn_count") or 0)
    threshold: Optional[float] = None
    currency: Optional[str] = None

    # R1: 解析失败 / 太少交易 — 整条流水没法用
    if parser in ("none", None) or txn_count < 3:
        rules.append({
            "code": "BANK_PARSE_FAIL",
            "severity": 3,  # critical
            "value": txn_count,
            "expected": 10,
            "suggestion_i18n_key": "bank_review.suggestion_parse_fail",
            "suggestion_params": {"got": txn_count},
        })
    else:
        # R2: 流水覆盖月数不足 (建议 ≥ 6)
        if coverage < 6:
            rules.append({
                "code": "BANK_COVERAGE_SHORT",
                "severity": 2,  # warning
                "value": coverage,
                "expected": 6,
                "suggestion_i18n_key": "bank_review.suggestion_coverage_short",
                "suggestion_params": {"got": coverage, "min": 6},
            })
        # R3: 余额低于建议值 (按目的国币种)
        threshold = _RECOMMENDED_BALANCE.get((destination or "").upper()) if destination else None
        currency = _DEST_CURRENCY.get((destination or "").upper()) if destination else None
        if threshold is not None and isinstance(ending, (int, float)):
            if ending < threshold:
                rules.append({
                    "code": "BANK_BALANCE_LOW",
                    "severity": 2,  # warning
                    "value": round(float(ending), 2),
                    "expected": threshold,
                    "currency": currency,
                    "destination": destination,
                    "suggestion_i18n_key": "bank_review.suggestion_balance_low",
                    "suggestion_params": {
                        "actual": round(float(ending), 2),
                        "actual_fmt": f"{ending:,.0f}",
                        "expected": threshold,
                        "expected_fmt": f"{threshold:,}",
                        "currency": currency or "",
                    },
                })
        # R4: 工资断档 (W52 已有 detect_income_gaps,这里做"最长一段"提示)
        if income_gaps:
            longest = max(income_gaps, key=lambda g: g.get("gap_months", 0))
            rules.append({
                "code": "BANK_INCOME_GAP",
                "severity": 2,  # warning
                "value": longest.get("gap_months"),
                "expected": 0,
                "start_month": longest.get("start_month"),
                "end_month": longest.get("end_month"),
                "suggestion_i18n_key": "bank_review.suggestion_income_gap",
                "suggestion_params": {
                    "months": longest.get("gap_months"),
                    "start": longest.get("start_month"),
                    "end": longest.get("end_month"),
                },
            })
        # R5: 大额进出 (>本地阈值),可能被签证官问资金来源
        if large_in or large_out:
            rules.append({
                "code": "BANK_LARGE_TXNS",
                "severity": 1,  # info
                "value": len(large_in) + len(large_out),
                "expected": 0,
                "in_count": len(large_in),
                "out_count": len(large_out),
                "suggestion_i18n_key": "bank_review.suggestion_large_txns",
                "suggestion_params": {
                    "in_count": len(large_in),
                    "out_count": len(large_out),
                },
            })
        # R6: 月均收入过低 (<当地常见 5,000 当地币种,简单硬编码;后面按 destination 算)
        if isinstance(monthly_income_avg, (int, float)) and monthly_income_avg < 5000:
            rules.append({
                "code": "BANK_INCOME_LOW",
                "severity": 1,  # info
                "value": round(float(monthly_income_avg), 2),
                "expected": 5000,
                "suggestion_i18n_key": "bank_review.suggestion_income_low",
                "suggestion_params": {
                    "actual": round(float(monthly_income_avg), 2),
                    "actual_fmt": f"{monthly_income_avg:,.0f}",
                    "min": 5000,
                },
            })

    # 按严重度倒序排
    rules.sort(key=lambda r: r.get("severity", 0), reverse=True)

    return {
        "rules": rules,
        "summary": {
            "balance_ok": (ending is not None and threshold is not None and ending >= threshold)
                          if threshold is not None else None,
            "coverage_ok": coverage >= 6,
            "income_gap_count": len(income_gaps),
            "large_txn_count": len(large_in) + len(large_out),
            "parse_ok": parser not in ("none", None) and txn_count >= 3,
        },
    }
