# Known Issues

未修复问题的记录，避免重复调查。发现即记录，暂不深挖修复，除非明确被要求处理。

## 1. pytest 全量回归会把 dev 数据库冲掉

**现象**：跑 `backend/.venv/bin/pytest tests/ -m "not slow"` 全量套件后，`backend/data/visa_mvp.db`
里的 `visa_destinations` / `rag_source` / `rag_chunk` 等表会被清空回初始状态（只剩 1 条 US
destination），即便这些表跟测试逻辑完全无关。**2026-07-02 追加确认**：`users` 表也会被清空——
跑一次全量套件后所有账号（包括手动创建的 demo 账号）都会消失，导致已登录用户的 access token 刷新
时报 "User not found"、被强制登出。

**已确认的触发条件**：`tests/integration/test_submit.py` + `tests/integration/test_w9_integration.py`
一起跑（哪怕只是这两个文件的子集）就能复现；单独跑任一个文件不会触发。`tests/integration/test_w7_integration.py`
加进去也会触发，说明不是这两个文件独有，可能是更广泛的 fixture/后台任务泄漏问题。

**怀疑根因（未验证到底）**：`app/services/payment_provider.py` 里的 "fire-and-forget" 自动通知任务
（`loop.create_task(self._auto_notify(...))`，模块级 `_PENDING_NOTIFIES` dict 持有引用，测试从不
await 它）。pytest-asyncio 是 `function` 级别的 event loop，如果这个任务在某个测试的 loop 关闭前
还没跑完，理论上不应该继续跑，但实际观察到的现象就是真实 dev db 文件被清空——具体是被清空还是被
"drop_all/create_all"重建，没有进一步验证。

**影响**：不影响自动化测试本身的正确性（测试用的是隔离的临时 SQLite），只影响本地手动跑全量测试后
需要重新跑一遍种子脚本才能让 dev 环境（浏览器里点的那个）恢复正常。

**Workaround**：跑完全量 pytest 后重新执行：
```bash
cd backend && source .venv/bin/activate
python3 scripts/seed_hero_destinations.py
python3 scripts/seed_schengen_26.py
PYTHONPATH=. python3 scripts/seed_rag_sources.py
# 再跑一次 refresh_all() 把 RAG chunk 填回去，参考 A_WORKLOG / 本次会话记录
```

**下一步（如果要修）**：先确认到底是 `_auto_notify` 泄漏,还是别的机制；可以先给
`test_submit.py`/`test_w9_integration.py` 加 `@pytest.mark.slow` 或在 payment_provider 里给
后台任务加 teardown-safe 的 cancel 逻辑。

---

## 2. W45 端到端自测发现的问题（2026-07-02，Claude 自测：选国家 → 材料向导 → LLM 行程 → 提交）

> 测试账号：`e2etester0702b` / `Test1234`（web 端注册，dev 库）。
> 测试路径：注册 → 登录 → /destinations 选 US → /materials-wizard 六大类上传+OCR →
> 行程单手填 + MiniMax 一键生成（真实调用成功）→ /orders/new OCR 预填 → 提交 →
> /rpa/submit → /orders/:orderNo。多语言 zh/en/vi/id 均切换验证。

### 2.1 有意留空（不修，等后续排期）

- **支付未接线**：步骤条显示 "4 Payment" 但 `OrderNew.vue:531` 注释 `Future: wire up "pay" → payment`，
  提交后直接跳 RPA；订单 `total_amount=0.00`；全 web 端无支付发起入口（只有 PaymentResult 落地页 + api wrapper）。
- **RPA 为假进度**：前端 /rpa/submit 显示 70% 是纯动画；后端任务卡 10% 且 `updated_at==created_at`（无 worker 消费）；
  `order.rpa_task_id=null`，订单状态停在 `created`。订单详情文案叫用户点"提交申请"但操作区没有该按钮（只有取消/返回）。

### 2.2 待修复 Bug

1. **work 签证标签显示成 Student** — `frontend/web/src/views/Destinations.vue:40`
   写死 `type === 'tourism' ? t('dest.tourism') : t('dest.student')`，AT/BE 等国显示 "Tourism · Student · Student"。
2. **英文局部下国家名显示代码** — 后端 `/api/v2/destinations?lang=en` 只有 AU/GB 返回英文名，
   其余（含 US）`country_name` 直接返回国家代码，卡片标题变成 "US"/"AT"/"HR"。中文正常。后端国家名翻译表不全。
3. **首页 hero 统计文案 4 语种全坏** — `frontend/web/src/views/Home.vue:54-66`
   用 `t('home.trust_stats.users', {n:''}).replace(/\+\s*$/,'')` hack，删不掉串首符号：
   EN 显示 "12,847+ + users served" / "99.2% % on-time delivery" / "4.9★ ★ user rating"；
   中文显示 "已服务 + 用户" / "准时出签 %" / "用户评分 ★"。应改成带参插值或拆 key，别用 replace。
4. **i18n 缺 key（console 500+ 条 intlify warn，回退英文）**：
   - `en` 缺：`nav.login`、`nav.mega.contact_i4`、`nav.mega.contact_i4_d`、`common.lang_switch_aria`
   - `id` 缺：`nav.logout`、`nav.orders_menu.*`（all/new_order/profile/materials）、
     `orderdetail.cancel_btn`、`orderdetail.back_btn`、`nav.mega.contact_i2_d/i3/i3_d/i4/i4_d`、`common.lang_switch_aria`
5. **行程表格表头英文局部重复** — `TravelPlanner.vue:70-75` 双语表头（本地语 + 硬编码英文 `<br/>Day`），
   locale=en 时显示 "Day/Day、Date/Date"。建议 locale 为 en 时不渲染第二行。
6. **材料向导进度条不实时** — 传完 3/3 项顶部仍显示 0%，点 Next 才跳 17%（每类占 1/6，应上传即涨或至少类内展示）。
7. **英文局部下 Bank Statement 提示用 "¥50,000"** — 人民币符号未随语种/目标国本地化。
8. **RPA 页步骤与百分比矛盾** — 显示步骤 1/3 (Visiting Portal) 却写 70%（假进度动画与步骤文案不同步，2.1 修 RPA 时一并处理）。

### 2.3 自测中确认正常的部分

注册/登录/token 持久化与跳转、材料向导六大类强校验顺序、上传+OCR（mock 识别 JOHN DOE/A12345678/2030-01-01）、
护照有效期读取、materials/diagnose、行程逐日表格编辑、**MiniMax 真实 LLM 生成**（交通 Day1 flight 后续 walk、
景点 Central Park/Times Square/Met、酒店 The Plaza Hotel）、OCR 预填申请表 100%、订单创建与详情时间线、
zh/en/vi/id 整页切换（向导/订单页翻译完整）。
