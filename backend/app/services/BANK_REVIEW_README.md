# Bank Statement Review Pipeline (W53 / W54 / W55 / W56)

签证材料"银行流水"的真实性审核流水线。从 OCR 文本到签证官能信的报告。

## 设计目标

签证官最怕的 3 种银行流水造假:

1. **余额链断链** — 缺页 / PS 改数字
2. **突击存入** — 申请前临时凑大额进账
3. **缺月** — 期间有月份消失(通常是被删的交易)

现有 `bank_statement_parser` 只做了"提取交易",W53+ 补完"审核真伪"。

## 模块

| 模块 | 职责 |
|------|------|
| `bank_statement_parser.py` | OCR → transactions[] + monthly_summary(W51, W53 加 Locale) |
| `balance_chain_check.py` | 余额链连续性 → ok / break / unknown(A 方案) |
| `material_group.py` | 多文件归组 + 页序还原 + 跨页去重 + missing_months |
| `financial_standard.py` | 目的国门槛 + 静态汇率换算 |
| `sudden_inflow.py` | 时序规则检测突击存入 |
| `visa_diagnoser.py` | 整合所有审核,产出诊断 issue |

## Locale 适配 (W53)

支持三个源国,千分位/小数/日期/方向词/币种/大额阈值全部本地化:

| Locale | 货币 | 千分位 | 小数 | 日期 | 大额阈值 |
|--------|------|-------|------|------|---------|
| CN | CNY | `,` | `.` | YYYY-MM-DD | 50,000 |
| VN | VND | `.` | `,` | DD/MM/YYYY | 50,000,000 |
| ID | IDR | `.` | `,` | DD/MM/YYYY | 50,000,000 |

未知国家 fallback 到 CN。

⚠️ **fallback 策略**(W56):CN 用户偶尔写 `01/03/2024` (dmy 口语),parser 自动 fallback 试全部 locale 顺序。

## A 方案: 余额字段缺失不报错

| 情况 | 行为 |
|------|------|
| 100% transaction 有 balance | 跑余额链检查,断链 → critical (≥5 笔) / warn (<5 笔) |
| 30%~99% 有 balance | 跑余额链检查 |
| < 30% 有 balance(常见:中国手机银行截图) | ok=None,severity=info,**不报 critical** |
| 0% 有 balance | 同上 |

## 入口

### 单文件/单 PDF

```python
from app.services.bank_statement_parser import parse_bank_statement

result = parse_bank_statement(ocr_items=ocr_items, source_country="VN")
# result = {
#     "transactions": [...],   # 每笔带 page 字段
#     "monthly_summary": [...],
#     "coverage_months": 3,
#     "missing_months": [],     # W54
#     "ending_balance": ...,
#     "parser": "regex"|"llm"|"none",
#     ...
# }
```

### 多文件/多页 PDF 完整流水线

```python
from app.services.material_group import MaterialItem, group_materials, review_group
from app.services.balance_chain_check import check_balance_chain, build_financial_report
from app.services.sudden_inflow import detect_sudden_inflows

# 1. 归组
items = [
    MaterialItem(material_id="m1", user_id=1, order_id=10,
                 material_type="bank", created_at=..., ocr_items=ocr_items1),
    MaterialItem(material_id="m2", user_id=1, order_id=10,
                 material_type="bank", created_at=..., ocr_items=ocr_items2),
]
groups = group_materials(items)
g = groups[0]

# 2. 完整 review(归组+页序+解析+去重+missing_months)
rev = review_group(g, source_country="VN")

# 3. 余额链
chain = check_balance_chain(rev["transactions"])

# 4. 突击存入
sudden = detect_sudden_inflows(rev["transactions"])

# 5. 余额达标判定
from app.services.financial_standard import evaluate_balance
verdict = evaluate_balance(
    ending_balance_src=rev["ending_balance"],
    source_country="VN",
    destination="SCHENGEN",
    stay_days=10,
)
```

### VisaDiagnoser 一站式

```python
from app.services.visa_diagnoser import VisaDiagnoser

# 把 rev 当 ocr_result 喂给 diagnoser
materials = [
    {"id": 1, "material_type": "passport", "ocr_status": "done",
     "ocr_result": {"passport_no": "E12345678", "expiry": "2030-12-31"}},
    {"id": 2, "material_type": "bank", "ocr_status": "done",
     "ocr_result": rev},
]
out = VisaDiagnoser().diagnose(
    materials=materials, country_code="VN", visa_type="tourism",
    fields={"destination": "SCHENGEN", "stay_days": 10}
)
# out.issues 里会包含:
#   - bank.balance_chain_break  (篡改 / 缺页)
#   - bank.months_missing       (月份不连续)
#   - bank.sudden_inflow        (突击存入)
#   - bank.balance_below_threshold (余额不达标)
#   - bank.income_gap / bank.large_inflow / bank.coverage_short 等
```

## 已知 issue codes

| Code | Severity | 含义 |
|------|----------|------|
| `bank.balance_chain_break` | warn / critical | 余额链断(≥5 笔 = critical) |
| `bank.balance_chain_low_coverage` | info | balance 字段覆盖率 < 30% |
| `bank.months_missing` | warn | 月份不连续(缺月) |
| `bank.sudden_inflow` | warn / high / hard_block | 申请前 N 天突击存入 |
| `bank.balance_below_threshold` | warn / block | 余额不满足目的国门槛 |
| `bank.income_gap` | warn | 工资断档 |
| `bank.large_inflow` | warn | 单笔大额转入 |
| `bank.coverage_short` | warn | 流水 < 3 个月 |
| `bank.unparseable` | warn | parser=none,无法结构化 |

## 配置 / 维护

- **目的国门槛** — `app/services/financial_standard.py` 的 `FINANCIAL_STANDARD_TABLE`
- **汇率表** — 同文件 `FX_RATES_TABLE`,as_of 注明日期,业务同学每月维护一次
- **大额阈值** — `LOCALE_TABLE[cc]["large_threshold"]`
- **时间窗(归组)** — `material_group.GROUP_TIME_WINDOW`(默认 30 分钟)

## 测试

```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_balance_chain_and_locale.py \
                    tests/unit/test_material_group_and_standard.py \
                    tests/unit/test_sudden_inflow.py \
                    tests/unit/test_e2e_pipeline.py \
                    tests/unit/test_visa_diagnoser.py -v
```

360 passed, 7 skipped (含 e2e 8 个 + locale 28 个 + 余额链 8 个 + 财务标准 11 个 + 突击存入 19 个 + diagnoser 40+)。