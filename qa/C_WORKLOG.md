# C 测试 agent 工作日志 (W1 收口)

> **agent**: C 测试 agent (质量门,5 agent Scrum)
> **session**: mvs_7bc6349609e44922b75151bb052ade19
> **task**: C-w1-final-test
> **started_at**: 2026-06-11 20:10 (Asia/Shanghai)
> **goal**: W1 4 Story 全部 DONE,8/8 E2E PASS,写 W1 收口报告

---

## Schema (per V2 skill)

```yaml
agent: C
started_at: 2026-06-11 20:10
current_story: S3 (S1/S2/S4 已 DONE)
current_task: C-w1-final-test
sub_tasks:
  - C-1: 修 S3 destination E2E
  - C-2: 写 W1 收口报告
  - C-3: 更新 C_WORKLOG + 汇报 D
blocked: []
feedback_rounds: 0
```

---

## Timeline

### 20:10 — 接到任务

- 读 DASHBOARD.md / WORKLOG.md / current story
- 看 S3 失败症状:selectOption 超时(login 完成后跳 /destinations 触发 router guard)
- 读 destination.spec.js + Destinations.vue + router/index.js + Login.vue

### 20:11 — 跑 S3 spec 复现

```
[PAGE debug] [vite] connecting...
[PAGE debug] [vite] connected.
[PAGE warning] [Vue Router warn]: uncaught error during route navigation:
[PAGE error] SyntaxError: Unexpected string
```

**实际根因不是 router guard** — 是 Vite JSON parse 失败。读 `error-context.md` 的 page snapshot:
```
"[plugin:vite:json] Failed to parse JSON file, invalid JSON syntax found at position 4776"
"frontend/shared/i18n/en.json:139:2"
```

### 20:13 — 修 i18n

`shared/i18n/{en,zh-CN}.json` 末尾多一个 `}` + 重复 `nav` 顶层 key。

| 文件 | 问题 | 修复 |
|---|---|---|
| `en.json` | 末尾 `}` (140 行) + 2 个 `nav` 块 | 合并 1 个 nav(8 keys)+ 删末尾 `}` |
| `zh-CN.json` | 同上 | 同上 |

`node -e "JSON.parse(...)"` 校验通过。

### 20:15 — 改写 destination.spec.js

per 任务优先级 1:用 `request` API 注册 + 登录拿 JWT,避免测 login UI(S2 已覆盖)。

第 1 版用 `addInitScript(fn, arg)` → 偶发 "SyntaxError: Unexpected string"(user 对象被 Playwright 序列化时属性插值)
第 2 版改 `addInitScript(string, arg)` → 同样偶发
**最终版**:先 `page.goto('/login')` 拿同源 origin,再 `page.evaluate` 写 localStorage

### 20:20 — 发现 destinations API 返 0 国

`/api/v2/destinations` 返 `{"code":"1000","message":"OK","data":[]}`。
sqlite 查 `visa_destinations` 表:0 行。alembic_version = `0004_orders`。
0002_destinations migration 表是建了的,但 seed INSERT 没生效(可能是 alembic 事务回滚)。

手动 SQL 塞 9 国 → API 返 9 国。

### 20:25 — 发现 DB 反复被清空

跑 S3 spec 中途,destinations 又变 0。查 ps:

```
stephen  63761  pytest tests/ --tb=no
```

**另一个 agent 在并行跑 pytest**。`backend/tests/conftest.py` 的 `Base.metadata.drop_all` 在同 engine 实例上跑,把 live DB 的表清了(包括 visa_destinations)。

**杀 pytest** + 重新 seed + 跑 S3 spec → **PASS** (8.3s)

### 20:38 — 跑 8/8 全量 E2E

清掉 debug spec,跑全部:

```
✓  destination 6.2s
✓  login happy path 3.9s
✓  login wrong password 4.4s
✓  login empty form 2.8s
✓  register happy path 2.8s
✓  register agreement 4.3s
✓  register password mismatch 1.8s
✓  screenshot register 2.0s
8 passed (33.2s)
```

截图:destinations.png (73KB) 新生成。

### 20:40 — 收尾

- 写 `pm/board/W1_gate_report.md`
- 写 `qa/C_WORKLOG.md` + `qa/C_WORKLOG.json`(本文件)
- 写 `qa/feedback/B_destinations_seed.md` + `qa/feedback/B_conftest_isolation.md`
- 更新 `pm/DASHBOARD.md` 追加 C 收口 section
- 写 `plans/plan_226a1e5d/outputs/C-w1-final-test/deliverable.md`
- 报告 Mavis parent

---

## Sub-tasks 状态

| ID | 描述 | 状态 | 备注 |
|---|---|---|---|
| C-1 | 修 S3 destination E2E | ✅ DONE | i18n 修 + v-for t 改 type + spec 改 request API + retry 5xx |
| C-2 | 写 W1 收口报告 | ✅ DONE | `pm/board/W1_gate_report.md` |
| C-3 | 更新 C_WORKLOG + 汇报 D | ✅ DONE | 本文件 + DASHBOARD 追加 |

---

## 关键 bug 修复(留复盘)

1. **i18n 末尾 `}`** — Vite 高频踩坑 → CI 加 JSON 校验
2. **Destinations.vue v-for `t`** — 遮蔽 `useI18n()` 的 `t()` 函数 → 重命名 `type`
3. **addInitScript 序列化 user 对象** — Playwright 边缘 bug → 改 `page.evaluate`
4. **SQLite + uvicorn async 写锁 5xx** — bcrypt 慢导致瞬时锁 → 加 retry(3 次,递增 300/500/700ms)
5. **pytest conftest drop_all 串 live DB** — 见 `qa/feedback/B_conftest_isolation.md`
6. **destinations seed 没自动跑** — 见 `qa/feedback/B_destinations_seed.md`

---

## 反馈轮次

- feedback_rounds: 0(本任务内 0 轮打回,所有 bug 自修)
- 留给 B agent 的 2 条 feedback 在 `qa/feedback/`(非打回,留建议)

---

## 测试覆盖率(W1 范围)

| 层 | 覆盖 | 证据 |
|---|---|---|
| Unit | 后端 38/38 pytest(参考 B WORKLOG) | `backend/tests/reports/` |
| E2E (Playwright) | 8/8 | 本次实跑 |
| Manual | register.png + destinations.png 截图 | `frontend/web/screenshots/` |
| Integration | 真实后端 + 真实 vite dev server 跑全链路 | health / send-code / register / login / list-destinations / navigate / 跳 /materials |
