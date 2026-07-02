# ADR-0006: LLM 资料诊断（付款前逻辑判断）—— 设计方案（未实现）

- **Status**: Proposed（设计稿，代码未接入 —— 未选定大模型服务商 / 未配置 API Key）
- **Date**: 2026-07-01
- **Scope**: Backend (`backend/app/services`, `backend/app/api/v2/materials.py`)

## Context

现有 `POST /api/v2/materials/diagnose`（`app/services/visa_diagnoser.py`）是一个**规则引擎 + RAG 文本参考**的诊断器，触发时机正确 —— 在订单 `created` 状态、支付前（付款成功才把订单从 `created` 推进到 `submitted`，见 `app/services/payment_provider.py:327-338`）。

`visa_diagnoser.py` 的模块 docstring 里已经写明了当初的设计取舍：

> Why rule-engine + RAG (not raw LLM)?
> - Deterministic baseline (testable, no hallucination on hard rules)
> - **LLM fallback optional later (when external API configured)**

也就是说 LLM 诊断从一开始就是预留但未填的坑。当前规则引擎能覆盖的是**结构化、确定性**的检查（材料是否齐全、护照有效期、护照号格式、OCR 是否失败），但覆盖不了需求里提到的**语义判断**：

- 银行流水金额是否异常（数额不匹配收入水平、大额单笔转入疑似凑数）
- 是否有敏感学校 / 专业 / 公司（如涉及被制裁院校、军工背景公司、放贷流水异常）

这类判断依赖对文本内容的语义理解，规则引擎和关键字匹配做不到，需要 LLM。

**代码库现状确认**（全项目 grep 结果）：`requirements.txt` 没有 `openai` / `anthropic` / `langchain` 等 SDK；没有任何 LLM client 封装、prompt 模板文件；`app/core/config.py` 没有任何 LLM 相关配置项。这个能力需要从零搭建。

**本次不实现的原因**：接入 LLM 需要先选定服务商（Anthropic / OpenAI / 国内厂商）并配置对应 API Key，这是产品/成本决策，不是纯技术决策，因此本次只产出设计方案，等选型确定后再排期开发。

## Decision（设计方案）

### 1. 总体架构 —— 在现有规则引擎基础上叠加一个 LLM 增强分支

不替换 `VisaDiagnoser`，而是新增一个独立的 `LLMMaterialAnalyzer`，两者并行跑，结果合并到同一个 `DiagnoseOutput`：

```
POST /api/v2/materials/diagnose
        │
        ├─ VisaDiagnoser.diagnose()        (现有，规则引擎，同步，快)
        │     → issues: completeness / passport expiry / ocr failed ...
        │
        └─ LLMMaterialAnalyzer.analyze()   (新增，异步调用 LLM，较慢)
              → issues: 流水异常 / 敏感学校专业公司 / 逻辑不一致
        │
        └─ 合并 issues + risk_score，一次性返回给前端
```

**为什么叠加而不是替换**：规则引擎的确定性检查（护照有效期、材料是否齐全）不需要 LLM，跑 LLM 反而增加延迟和不确定性；LLM 只负责规则引擎做不到的语义判断。两者失败域也不同——规则引擎几乎不会挂，LLM 调用可能超时/限流，需要能优雅降级（LLM 调用失败时,仍返回规则引擎的结果，只是少了语义诊断部分，不阻塞用户提交流程）。

### 2. 新增文件清单

| 文件 | 职责 |
| --- | --- |
| `app/services/llm/client.py` | LLM client 薄封装：`async def complete(prompt, *, max_tokens, temperature) -> str`。屏蔽具体厂商 SDK 差异,方便后续换供应商。 |
| `app/services/llm/prompts/material_diagnosis.py` | Prompt 模板 + few-shot 示例,输出结构用 JSON schema 约束（避免自由文本解析）。 |
| `app/services/llm_material_analyzer.py` | 业务编排层：拼装材料内容（OCR raw_text + 结构化字段）→ 调 LLM → 解析 JSON → 转成 `DiagnoseIssue` 列表,复用 `visa_diagnoser.py` 里已有的 `DiagnoseIssue` / severity 体系,不新造一套。 |
| `app/core/config.py` | 新增配置段（见下）。 |
| `.env.example` | 新增 `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` 占位。 |
| `tests/unit/test_llm_material_analyzer.py` | mock LLM client,测试 prompt 拼装、JSON 解析、异常降级路径。**不在测试里真实调用 LLM**（成本 + 不确定性）。 |

### 3. Config 新增项（`app/core/config.py`）

```python
# --- LLM material diagnosis (optional, opt-in) ---
llm_diagnosis_enabled: bool = False          # 总开关,未配置 key 时必须是 False
llm_provider: Literal["anthropic", "openai", "none"] = "none"
llm_api_key: Optional[str] = None            # 从 env 读,不落 DB/日志
llm_model: str = ""                          # 具体走哪个模型,由服务商决定
llm_timeout_seconds: float = 20.0
llm_max_tokens: int = 1024
```

`llm_diagnosis_enabled=False` 且 `llm_api_key` 为空时，`LLMMaterialAnalyzer.analyze()` 直接跳过（返回空 issue 列表），`materials.diagnose` 端点行为与今天完全一致 —— 这保证了在没有选型/没有 Key 之前，接入这段代码本身也是安全的（不会因为缺配置报错）。

### 4. 与现有 `visa_diagnoser.py` / `/materials/diagnose` 的集成点

在 `app/api/v2/materials.py::diagnose()`（当前第 354-418 行）里，`VisaDiagnoser().diagnose(...)` 调用之后加一段：

```python
out = diagnoser.diagnose(...)                      # 现有规则引擎,不变

if settings.llm_diagnosis_enabled:
    llm_issues = await LLMMaterialAnalyzer().analyze(
        materials=materials,       # 复用同一份 materials dict list
        country_code=body.country_code,
        visa_type=body.visa_type,
    )
    out.issues.extend(llm_issues)
    out.risk_score = _recompute_risk_score(out.issues)  # 复用 visa_diagnoser._SEVERITY_WEIGHT
```

`DiagnoseIssue` 的 `code` 前缀用 `llm.*`（如 `llm.bank_flow_anomaly` / `llm.sensitive_school` / `llm.sensitive_company`），方便前端/日志区分是规则引擎还是 LLM 判断出来的问题，也方便后续单独统计 LLM 判断的准确率。

### 5. 需要先扩展的材料字段（否则 LLM 拿不到足够输入）

当前 `material_classifier.py` / `ocr.py` 对"银行流水"没有专门的结构化抽取（金额、交易记录），"学校/专业/公司"也没有结构化字段，只有 OCR 的 `raw_text`（`app/services/ocr.py:608`）。两个选项：

- **选项 A（推荐，改动小）**：直接把 OCR `raw_text` 整段喂给 LLM，让 LLM 自己从非结构化文本里提取金额/机构名并判断，不改 OCR 抽取逻辑。缺点是依赖 LLM 的文本理解能力,成本略高（更多 token）。
- **选项 B（改动大）**：先在 `ocr.py` / `material_classifier.py` 里新增银行流水金额正则抽取、学校/公司名 NER,结构化后再喂给 LLM 做语义判断。更省 token、更可控,但要先做字段抽取的开发和测试。

建议先上选项 A 验证效果，跑一段时间看 LLM 判断质量，如果误判多或者 token 成本高，再补选项 B 的结构化抽取。

### 6. Prompt 设计要点（`material_diagnosis.py`）

- **强制 JSON 输出**（用 Claude 的 tool use / OpenAI 的 JSON mode，不用自由文本 + 正则解析，避免解析失败）。
- **输出 schema**：
  ```json
  {
    "issues": [
      {
        "code": "bank_flow_anomaly",
        "severity": "warning|error",
        "title": "...",
        "detail": "...",
        "confidence": 0.0
      }
    ]
  }
  ```
- **明确让模型只标记「值得签证官关注的异常」，不做武断的通过/拒绝判断** —— LLM 是风险提示工具，不是签证决策者，最终决定权在用户和人工审核，这个措辞要写进 system prompt，避免用户误以为是官方判定。
- **输入长度控制**：单个材料 raw_text 超过一定长度（如 4000 字符）要截断或摘要，避免超出模型上下文/成本失控。

### 7. 失败降级策略

- LLM 调用超时/报错 → 记录日志，返回空 issue 列表，**不影响规则引擎结果**，`materials.diagnose` 接口整体仍然 200。
- 复用 `app/services/rag/refresh.py` 里"best-effort，失败不阻断主流程"的既有模式（`visa_diagnoser._fetch_policy_refs` 已经是这个模式，可以照抄）。

### 8. 测试策略

- **不真实调 LLM**：mock `LLMClient.complete()`，喂固定 JSON 响应，测 `LLMMaterialAnalyzer` 的解析/降级逻辑。
- 覆盖：正常解析、JSON 格式错误的容错、超时降级、`llm_diagnosis_enabled=False` 时跳过。
- 集成测试补一条：`/materials/diagnose` 在 `llm_diagnosis_enabled=False`（默认）时行为与今天完全一致（回归保护，防止以后有人不小心把默认值改成 True）。

## Consequences

### Positive
- 复用现有 `DiagnoseIssue` / risk_score 体系，前端零改动即可展示 LLM 发现的问题。
- Config 开关 + 空 Key 默认关闭，合入代码本身不引入风险，可以先合并骨架代码（client 封装 + 空跳过逻辑），选型定了再补真实 Key 上线。
- 失败降级设计保证 LLM 服务抖动不影响用户主流程（付款前的提交仍然可用）。

### Negative / Trade-offs
- 需要选型 + 付费 API，是持续性成本（每次诊断调用都要花 token），需要产品侧评估 ROI。
- 选项 A（喂 raw_text）对长文档 token 消耗较大；选项 B 需要额外开发结构化抽取。
- LLM 输出的语义判断存在误判风险（尤其"敏感学校/专业/公司"这种主观性较强的判断），需要有反馈机制让用户可以标记"误判"，否则可能积累用户不信任。

### Reversibility
高。整个功能是通过 `llm_diagnosis_enabled` 开关控制的旁路增强，出问题可以直接关开关回退到纯规则引擎，不影响 `VisaDiagnoser` 原有代码。

## References
- `backend/app/services/visa_diagnoser.py` —— 现有规则引擎，本设计复用其 `DiagnoseIssue` 结构。
- `backend/app/api/v2/materials.py:349-418` —— `/materials/diagnose` 端点，集成点所在。
- `backend/app/services/payment_provider.py:327-338` —— 确认诊断发生在付款之前（`created` → `submitted` 由支付成功驱动）。
- `backend/app/services/ocr.py:608` —— OCR `raw_text`，选项 A 的输入来源。
- `backend/app/services/rag/refresh.py` —— best-effort 失败降级模式参考。
