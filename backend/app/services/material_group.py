"""材料归组 + 多页流水审核管线 (W54)

一份银行流水经常被拆成多个文件:
  - 一个 5 页 PDF
  - 多张手机银行截图(每张一页)
  - PDF + 几张补图

归组 grouping 决定这些文件是否属于"同一份流水"。
页序还原 ordering 决定页与页之间的拼接顺序。
跨页去重 dedup 避免相邻页重复行导致余额链误断。

归组策略 (W54 v1)
-----------------
按以下信号分组 (优先级从高到低):
  1. **同一个 material.id** -> 单文件 / 单 PDF 自动 1 个 group
  2. **同一个 order_id + material_type + 同 upload batch(短时间窗)**
     -> 用户可能在 10 分钟内连续上传同一份流水的 3 张图,合并为一组
  3. **同名/同 sha256** -> 同文件不会重复建组(已经有 sha256 唯一索引)

W54 v1 简化:
  - 只支持同 material_type='bank' 的归组
  - 同 user_id + order_id + material_type + 时间窗 (默认 30 分钟) 视为同一份流水
  - 后续可加 LLM 指纹比对 (银行 logo / 账号尾号),放 P2

页序还原 ordering
-----------------
  - PDF: 按 page_index 升序
  - 散图: OCR 文本里的 "Page x/y" 或 "Trang x/y" (越南) / "Halaman x/y" (印尼) 抽出 x;
          没 footer 时按 date 递增(最旧在前)
  - 兜底: 按 created_at 升序(上传顺序)

跨页去重 dedup
--------------
  - key = (date, amount, balance_or_none)
  - 同 key 出现多次 (跨页边界重复) -> 保留首条,删除后面
  - 边界 5px / 1 行 内的相邻重复(同 date + 同 amount + balance 接近) -> 一并合并

输出
----
每个 group 一个 `MaterialGroup` dataclass:
    {
      group_id, material_type, items: [(material_dict, page_text, page_no)],
      ordered_pages: [(page_no, text)],
      merged_transactions: [...]  # 跨页拼接 + 去重后的 transactions
    }
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# 阈值                                                                #
# ---------------------------------------------------------------- #
# 同一份流水的上传时间窗(默认 30 分钟)
GROUP_TIME_WINDOW = timedelta(minutes=30)

# 跨页去重: balance 容差
DEDUP_BALANCE_TOLERANCE = 0.02

# 页脚 "Page x/y" 关键词(中/英/越/印尼)
PAGE_FOOTER_PATTERNS = [
    re.compile(r"(?:Page|Trang|Halaman|Halaman|Página)\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE),
    re.compile(r"页码[:\s]*(\d+)\s*/\s*(\d+)"),
    re.compile(r"第\s*(\d+)\s*页\s*/\s*共\s*(\d+)\s*页"),
]


# ---------------------------------------------------------------- #
# 数据结构                                                            #
# ---------------------------------------------------------------- #
@dataclass
class MaterialItem:
    """一个材料上传条目(可以是 OCR 后的 material,或 ocr_items 列表)。"""
    material_id: str
    user_id: int
    order_id: Optional[int]
    material_type: str
    created_at: datetime
    ocr_items: Optional[List[Dict[str, Any]]] = None  # [{text, bbox, page_index?, confidence}, ...]
    ocr_text: Optional[str] = None  # 已经转好的纯文本(单页场景)
    page_count: int = 1  # PDF 页数 / 散图张数


@dataclass
class MaterialGroup:
    """同一份流水的归组结果。"""
    group_id: str
    material_type: str
    user_id: int
    order_id: Optional[int]
    items: List[MaterialItem] = field(default_factory=list)
    # 排序后的页面 [(page_no, text, source_material_id)]
    ordered_pages: List[Tuple[int, str, str]] = field(default_factory=list)
    # 跨页拼接 + 去重后的 transactions(从 ordered_pages 喂给 parser)
    merged_transactions: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.ordered_pages)


# ---------------------------------------------------------------- #
# 归组                                                                #
# ---------------------------------------------------------------- #
def group_materials(
    items: List[MaterialItem],
    *,
    time_window: timedelta = GROUP_TIME_WINDOW,
) -> List[MaterialGroup]:
    """按 (user_id, order_id, material_type, upload_batch) 归组。

    Args:
        items: 候选材料列表(只处理 material_type='bank')
        time_window: 同组的时间窗(默认 30 分钟)

    Returns:
        一组 MaterialGroup,每组包含 N 个 MaterialItem。
    """
    # 只归组 bank(后续可扩展到 employment / passport 等)
    bank_items = [it for it in items if (it.material_type or "").lower() == "bank"]
    if not bank_items:
        return []

    # 按 (user_id, order_id, material_type, batch_key) 分组
    # batch_key = created_at 落到 time_window 的 bucket
    bank_items.sort(key=lambda it: (it.user_id, it.order_id or 0, it.created_at))
    groups: List[MaterialGroup] = []
    current: List[MaterialItem] = []

    for it in bank_items:
        if not current:
            current = [it]
            continue
        last = current[-1]
        same_owner = (it.user_id == last.user_id and it.order_id == last.order_id)
        same_type = it.material_type == last.material_type
        in_window = (it.created_at - last.created_at) <= time_window
        if same_owner and same_type and in_window:
            current.append(it)
        else:
            groups.append(_build_group(current))
            current = [it]
    if current:
        groups.append(_build_group(current))
    return groups


def _build_group(items: List[MaterialItem]) -> MaterialGroup:
    """把一组 MaterialItem 包成 MaterialGroup + 计算 group_id。"""
    first = items[0]
    # group_id = user + order + type + 时间窗起始 hash(去重友好)
    sig = f"{first.user_id}|{first.order_id or 0}|{first.material_type}|{first.created_at.timestamp()}"
    group_id = "g_" + hashlib.sha1(sig.encode()).hexdigest()[:12]

    g = MaterialGroup(
        group_id=group_id,
        material_type=first.material_type,
        user_id=first.user_id,
        order_id=first.order_id,
        items=list(items),
    )
    # 自动排序 + 还原页序
    g.ordered_pages = restore_page_order(items)
    return g


# ---------------------------------------------------------------- #
# 页序还原                                                            #
# ---------------------------------------------------------------- #
def restore_page_order(items: List[MaterialItem]) -> List[Tuple[int, str, str]]:
    """把多份材料的页面排序成统一序列。

    Returns:
        [(global_page_no, page_text, source_material_id), ...]
        global_page_no 从 1 开始递增(按时间+原始页码重排)。
    """
    # 中间结构: (sort_key, page_no_in_material, text, material_id)
    pages: List[Tuple[Tuple, int, str, str]] = []
    for mi in items:
        if mi.ocr_items:
            # 多页材料: 按 page_index 拆
            per_page_text = ocr_items_group_by_page(mi.ocr_items)
            for page_idx in sorted(per_page_text.keys()):
                txt = per_page_text[page_idx]
                pages.append((_sort_key_for(mi, page_idx), page_idx, txt, mi.material_id))
        elif mi.ocr_text:
            # 单页 / 已拼好的文本
            page_no = _detect_page_footer(mi.ocr_text) or 1
            pages.append((_sort_key_for(mi, page_no), page_no, mi.ocr_text, mi.material_id))
    # 排序: sort_key 升序(更早/更前的在前);同 sort_key 内按原始页码
    pages.sort(key=lambda x: (x[0], x[1]))
    # 重编号为 global page_no
    return [(i + 1, txt, mid) for i, (_, _, txt, mid) in enumerate(pages)]


def _sort_key_for(item: MaterialItem, page_no: int) -> Tuple:
    """综合排序键:(created_at, page_index)。

    - created_at 让多个文件按上传时间排
    - page_index 让多页文件按页码排
    """
    return (item.created_at.timestamp(), page_no)


def ocr_items_group_by_page(items: Iterable[Dict[str, Any]]) -> Dict[int, str]:
    """把 OCR items 按 page_index 分组,每组内按行聚合成文本。

    没 page_index 的 items 归到 page 1 (向后兼容)。
    """
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for it in items:
        p = int(it.get("page_index") or 1)
        by_page.setdefault(p, []).append(it)
    out: Dict[int, str] = {}
    for p, page_items in by_page.items():
        out[p] = ocr_items_to_text_for_page(page_items)
    return out


def ocr_items_to_text_for_page(items: Iterable[Dict[str, Any]]) -> str:
    """单页内的 OCR items → 文本(走原有行聚类逻辑)。

    这是 ocr_items_to_text 的"单页版",逻辑一致但签名更明确。
    """
    from app.services.bank_statement_parser import ocr_items_to_text
    return ocr_items_to_text(items)


def _detect_page_footer(text: str) -> Optional[int]:
    """从 OCR 文本里识别"Page x/y"格式的页码,返回 x;识别不到返 None。"""
    if not text:
        return None
    # 先搜最后几行(页脚通常在最底)
    lines = text.splitlines()[-5:] if text else []
    for line in lines:
        for pat in PAGE_FOOTER_PATTERNS:
            m = pat.search(line)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, IndexError):
                    continue
    # 整页搜(兜底)
    for pat in PAGE_FOOTER_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                return int(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


# ---------------------------------------------------------------- #
# 跨页拼接 + 去重                                                     #
# ---------------------------------------------------------------- #
def dedup_transactions(
    transactions: List[Dict[str, Any]],
    *,
    balance_tol: float = DEDUP_BALANCE_TOLERANCE,
) -> Tuple[List[Dict[str, Any]], int]:
    """跨页去重 — 同一 (date, amount, balance) 重复出现的只保留首条。

    Args:
        transactions: 跨页拼接后的 transactions(已经按 page 顺序)
        balance_tol: balance 字段容差

    Returns:
        (deduped_transactions, removed_count)
    """
    seen: Dict[Tuple, int] = {}  # key -> first index
    out: List[Dict[str, Any]] = []
    removed = 0
    for i, t in enumerate(transactions):
        key = _dedup_key(t, balance_tol=balance_tol)
        if key is None:
            # 无 key(缺字段)还是保留
            out.append(t)
            continue
        if key in seen:
            removed += 1
            continue
        seen[key] = i
        out.append(t)
    return out, removed


def _dedup_key(t: Dict[str, Any], *, balance_tol: float) -> Optional[Tuple]:
    """去重 key = (date, amount, balance_bucket)。

    balance_bucket: 把 balance 量化到 1/tol 精度,容忍小浮点误差。
    """
    d = t.get("date")
    amount = t.get("amount")
    if not d or amount is None:
        return None
    balance = t.get("balance")
    if balance is None:
        bal_bucket = ("none",)
    else:
        bucket = int(round(float(balance) / balance_tol))
        bal_bucket = ("bal", bucket)
    return (str(d), round(float(amount), 2), bal_bucket)


# ---------------------------------------------------------------- #
# months 连续性检查                                                    #
# ---------------------------------------------------------------- #
def detect_missing_months(monthly_summary: List[Dict[str, Any]]) -> List[str]:
    """从 monthly_summary 找缺月(假设覆盖期是连续的)。

    例: monthly_summary = [{month:'2024-03'}, {month:'2024-06'}, ...]
        -> 缺 ['2024-04', '2024-05']

    Args:
        monthly_summary: aggregate 出的 [{month, income, ...}, ...]

    Returns:
        缺失月份的 ['YYYY-MM', ...] 列表(按时间升序)
    """
    if not monthly_summary or len(monthly_summary) < 2:
        return []
    months = sorted({m["month"] for m in monthly_summary if m.get("month")})
    if len(months) < 2:
        return []
    missing: List[str] = []
    for i in range(len(months) - 1):
        gap = _months_between(months[i], months[i + 1])
        if gap > 1:
            # 月份差 > 1 -> 中间缺
            for j in range(1, gap):
                missing.append(_add_months(months[i], j))
    return missing


def _months_between(start_month: str, end_month: str) -> int:
    """两个 YYYY-MM 之间相差几个月(end - start)。"""
    try:
        sy, sm = int(start_month[:4]), int(start_month[5:7])
        ey, em = int(end_month[:4]), int(end_month[5:7])
        return (ey - sy) * 12 + (em - sm)
    except (ValueError, IndexError):
        return 0


def _add_months(month_str: str, delta: int) -> str:
    """YYYY-MM + delta 月。"""
    try:
        y, m = int(month_str[:4]), int(month_str[5:7])
        total = y * 12 + (m - 1) + delta
        ny, nm = divmod(total, 12)
        return f"{ny:04d}-{nm + 1:02d}"
    except (ValueError, IndexError):
        return month_str


# ---------------------------------------------------------------- #
# 一站式:把 ordered_pages 喂给 parser,做完整 group review            #
# ---------------------------------------------------------------- #
def review_group(
    group: MaterialGroup,
    *,
    source_country: str = "CN",
) -> Dict[str, Any]:
    """对整个 group 跑完整审核流水线:
      1. 把 ordered_pages 喂给 bank_statement_parser 逐页解析
      2. 跨页拼接 + 去重
      3. aggregate 出 monthly_summary + balance chain
      4. 检查 missing_months

    Args:
        group: MaterialGroup
        source_country: CN|VN|ID

    Returns:
        完整的解析结果(可以直接喂给 visa_diagnoser):
        {
            "transactions": [...],
            "monthly_summary": [...],
            "coverage_months": int,
            "missing_months": [...],
            "ending_balance": ...,
            "large_inflows": [...],
            "parser": "regex"|"llm"|"none",
            "confidence": 0..1,
            "page_count": int,
            "dedup_removed": int,
        }
    """
    from app.services.bank_statement_parser import parse_with_regex, aggregate

    all_txns: List[Dict[str, Any]] = []
    parser_used = "none"
    confidence = 0.0

    # 每页单独解析 -> 每页 transaction 带 page 字段
    for page_no, text, _mid in group.ordered_pages:
        if not text:
            continue
        page_txns = parse_with_regex(text, source_country=source_country)
        for t in page_txns:
            t["page"] = page_no
        all_txns.extend(page_txns)

    if all_txns:
        parser_used = "regex"
        confidence = 0.7 if len(all_txns) >= 10 else 0.4

    # 跨页去重
    deduped, removed = dedup_transactions(all_txns)

    # aggregate
    agg = aggregate(deduped, source_country=source_country)
    agg["transactions"] = deduped
    agg["parser"] = parser_used
    agg["confidence"] = confidence
    agg["page_count"] = group.page_count
    agg["dedup_removed"] = removed

    # missing_months
    agg["missing_months"] = detect_missing_months(agg.get("monthly_summary") or [])

    return agg