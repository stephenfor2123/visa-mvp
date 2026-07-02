# W15 Sprint 最小可行路线图

> owner: PM coder
> 适用: W15 本周 (2026-06-14 ~ 2026-06-20)
> 来源: pm/board/W14_summary.md (292 行, 4 PASS / 7 代码已落盘无 deliverable)
> 体例: 同 W14_summary, 任务 <=1 行 title + owner + 估算小时

---

## §1 W15 主题

W14 收口 + 关键 bug 修复。本周把 11 个 W14 task 全部转为 PASS (含 7 个 verify-only retry), 同时修复阻塞 W16/W17 进展的 3 个 pre-existing bug (venv 死链 / i18n id.json 末尾多余右花括号 / vite build hang)。严格不复制 W14 worklog / A_WORKLOG / C_WORKLOG 内容 (历史占位污染源), 也不引用 .mavis/plans/*.yaml 历史 plan。

---

## §2 W15 任务列表 (10 条)

| # | 任务 | 优先级 | 耗时 | 依赖 | Owner |
|---|------|--------|------|------|-------|
| W15-1 | 重建 backend .venv (或找真 venv Python), pytest 早失败检测 | P0 | 1h | 无 | Coder |
| W15-2 | 修 i18n id.json 末尾多余右花括号 (删第 631 行孤立括号, 全 4 语种 json.load 验证) | P0 | 15min | 无 | Coder |
| W15-3 | W14-2 RPA retry verify-only: 补 deliverable.md + uvicorn 实测 + 重跑 pytest | P0 | 30min | W15-1 | Coder |
| W15-4 | W14-3 admin retry verify-only: 补 deliverable.md + curl login 端点 + 重跑 pytest | P0 | 30min | W15-1 | Coder |
| W15-5 | W14-4 前端 RPA retry verify-only: 补 deliverable.md + npm build 旁路方案 + 截图 (避开 vite hang) | P0 | 45min | W15-1 | Coder |
| W15-6 | W14-5 voice retry verify-only: 补 deliverable.md + VoiceRecorder.vue 落盘 | P0 | 1h | W15-1 | Coder |
| W15-7 | W14-6 ratelimit + W14-10 payment + W14-11 admin login retry verify-only: 补 3 个 deliverable + 截图 | P1 | 1.5h | W15-5 | Coder |
| W15-8 | 清理 ci.yml 历史占位注释 + cleanup-residual 残余 202 行历史占位 | P2 | 1.5h | 无 | Coder |
| W15-9 | W14_summary 修正 sha256 索引 (deliverable 实际 wc 与 claim 偏差需修) | P2 | 30min | W15-3 | Coder |
| W15-10 | W15 收口报告 pm/board/W15_summary.md | P2 | 30min | W15-3 ~ W15-9 | Coder |

> 总耗时: 约 8.5h Coder (W15-3 至 W15-7 用 verify-only retry 模板: 代码已落盘, 只补 deliverable + 重跑 verify, 5min 内必出)。

---

## §3 阻塞 W15 的 3 个 pre-existing bug + 旁路方案

### B1 - venv 死链 (P0 必修)

症状: backend/.venv/bin/python3 symlink 链到 CommandLineTools system Python 而非 venv Python, import sqlalchemy / pydantic 时 hang。
检测: ls -la backend/.venv/bin/python*, 看 python3 是否链到 venv 内。
修复: rm -rf backend/.venv && python3 -m venv backend/.venv && pip install -r requirements.txt。
预防: pytest 前加 python -c "import sys; assert .venv in sys.executable" 早失败。

### B2 - i18n id.json 末尾多余右花括号 (P0 必修)

症状: frontend/shared/i18n/id.json 第 631 行有孤立右花括号, python3 json.load 失败, 印尼语页面空白。
修复: 删除第 631 行孤立右花括号 + 全 4 语种 json.load 验证 PASS。
影响: 阻断 1/4 用户 (印度尼西亚约 270M 人口)。

### B3 - vite build hang on macOS (P1 旁路方案)

症状: npm run build 在 M 系列 macOS 上静默挂起 (>5min 无输出), 多 worker 并发累积 zombie vite 进程。
旁路 (不真跑 build 也能收口): 用 AST parse + JSON load 验证代码完整性, 跳过实际 build / 截图用 Playwright headless 或 mavis browser tool 走真实 URL。
真实 build 留给 CI runner (ci.yml 的 frontend-playwright job) 或装 Docker Desktop 后 npx vite build --logLevel info。

---

## §4 不做的事 (W15 范围外)

- W16/W17 详细规划: 留给 W15-3 后的子 sprint 单独写; 本 roadmap 只标 W15 本周范围。
- 不重写 W14 代码: W14 task 代码已 on disk, 仅补 deliverable + verify-only retry。
- 不引用历史 worklog / .mavis/plans/*.yaml / A_WORKLOG / C_WORKLOG: 历史占位污染源, 直接绕开。
- 不真跑 npm build: 走 §3 B3 旁路方案 (AST + JSON + Playwright headless 截图)。
- 不做 Stripe 真接 / Apple 上架凭据对接: 真人决策, 等 W16 用户提供凭据。

---

## §5 风险 (3 条)

| # | 风险 | 严重度 | 触发条件 | 缓解 |
|---|------|--------|----------|------|
| W15-R1 | venv 重建后 pytest 仍 hang (system Python 与 venv Python 架构兼容问题) | P1 | macOS arm64/x86_64 不匹配 | which python3.9 找其他 venv Python; 不行则走 SQLite --noconftest fallback (W14-1 已验) |
| W15-R2 | W14 retry cap-kill 30min 仍缺 deliverable | P2 | verify-only 仍超时 (zombie vite 进程占资源) | W15-5 前 pkill -f vite 清场; 单 deliverable 拆细到 <=10min |
| W15-R3 | 7 个 verify-only 同时跑共享 venv 资源争抢 | P2 | W15-3/4/6/7 都依赖 W15-1 修复后 venv | W15-3/4 串行 (共用 venv import), W15-5/7 可并行 (前端) |

---

## §6 真人决策点 (W15 范围内: 0; 跨 sprint 范围: 6)

W15 范围内没有真人决策 (全部 Coder verify-only retry)。

跨 sprint 决策 (留给 W16 用户拍板):
- D1: Apple 开发者账号 + iOS Keychain 凭据
- D2: Google Play Console 账号 + 内测包签名
- D3: Stripe sk_test_xxx 真接凭据
- D4-D5: 印尼 / 越南本地律师 review
- D6: admin_password secret manager 选型

---

## §7 关键路径

```
W15-1 (venv) --+--> W15-3 (RPA) --> W15-9 (sha256 修正) --> W15-10 (W15_summary)
             +--> W15-4 (admin) ----+
             +--> W15-6 (voice) ----+
             +--> W15-2 (i18n) --> W15-5 (frontend build 旁路) --> W15-7 (3 retry) ----+
```

W15-1 venv 修复是 W15-3/4/6 的共同前置, 必须先做。

---

## §8 数据源 + 节奏对齐

- W14 总结: pm/board/W14_summary.md (292 行, 4 PASS / 7 代码已落盘无 deliverable)
- 风险登记: pm/risks/risks.md (12 条)
- WBS: pm/wbs/wbs.md (129 任务 / W1-W8)
- Agent memory: ~/.mavis/agents/coder/memory/MEMORY.md (8 条 W14 经验)
- W15 出口: 11/11 W14 task 全部 PASS, i18n 4 语种 json.load 全 PASS, venv 可跑 pytest
