# D-VERIFY-RUNNER 真值 grep recipe (D 失察修整 recipe)

> **修整背景**: 2026-06-12 W6b 17:54 + W8 21:49 + W9 22:53 + W9 23:10 + W10 23:55 共 5 次 D 失察 — D Coordinator 跑 4 必查时漏查 1 P0 (deliverable.md / A_WORKLOG.md / screenshots sha256 / pytest 缺任一)。W11-2 修整 (本任务) 修整文档化 recipe, W12+ 每 plan_yaml verify_prompt 必带 "run D-VERIFY-RUNNER" 强制约束。

## 1. 4 必查 — wire-level recipe

每个 producer 任务收口时, D verifier (或 D 自身) 必跑以下 4 步, **任一 FAIL 即整体 FAIL**:

### Step 1 — 截图 sha256 distinct (反 W6b A-W6-4 教训)
```bash
sha256sum frontend/web/screenshots/**/*screenshot*.png 2>/dev/null | \
  awk '{print $1}' | sort -u | wc -l
# 对比 screenshot 总数:
find frontend/web/screenshots/ -name "*screenshot*.png" 2>/dev/null | wc -l
# 期望: distinct == total (每个图 hash 都不同)
```

### Step 2 — deliverable.md 必存在非空
```bash
test -s outputs/<TASK_ID>/deliverable.md && \
  wc -l outputs/<TASK_ID>/deliverable.md
# 期望: 0 退出 + 行数 > 30 (避免 stub deliverable)
```

### Step 3 — WORKLOG 必追加任务对应行
```bash
grep "<TASK_ID>" backend/WORKLOG.md   # 或 frontend/A_WORKLOG.md
# 期望: 至少 1 行命中, 行内含 task_id 字符串
```

### Step 4 — 核心功能 wire-level 验证 (subprocess.run 真输出)
```bash
# 后端: pytest 跑 + 数字回报
.venv/bin/pytest tests/integration/<feature>.py -v 2>&1 | tail -5
# 前端: npm build + 截图
cd frontend/web && npm run build 2>&1 | tail -3
# 跨子系统: curl 真端到端
curl -s http://localhost:8000/api/v2/health | jq .
```

## 2. 修整 #1 — D 漏查根因

- **W6b 17:54**: 漏查 `deliverable.md` 不存在 — D override_accept 时只 Read producer 主报告, 没跑 Step 2。
- **W8 21:49**: 漏查 `A_WORKLOG.md` 缺 W8 行 — D 凭印象 "producer 应该追加了", 没跑 Step 3。
- **W9 22:53**: 漏查 `screenshots sha256 distinct` — 3 张图实际同图, D 没跑 Step 1 实证。
- **W9 23:10**: 漏查 pytest 缺 1 case — D 看 producer "9/9 PASS" 没跑 Step 4 复跑。
- **W10 23:55**: 漏查 `output/B-W10-4/deliverable.md` 段位错配 (写 V2.1 Stripe 但只 Mock 落地) — D 没跑 Step 2 逐段读。

**共同根因**: D 跑 4 必查时靠"印象" + "短 Read", 不是 wire-level 真命令。

## 3. 修整 — 工具化

- **C-W11-3 (本 sprint W11 sub-task 3)**: 写 `tools/d-verify-runner.sh` 跑 4 必查, 输出 PASS/FAIL + 数字。
- **本文件**: 修整 #1 文档化 recipe, 给 D 自身 + W12+ producer 读, 防止 5+1 次失察。

## 4. 4 必查 PASS 判据 (反例 + 正例)

| Step | FAIL 反例 | PASS 正例 |
|------|----------|----------|
| 1. sha256 distinct | 3 张图 sha256 全撞 (W6b 教训) | 12 张图 sha256 两两不同 |
| 2. deliverable.md 存在非空 | 0 byte 或不存在 | ≥ 30 行, 含 4 必查 PASS 表 |
| 3. WORKLOG grep 命中 | producer 忘了 append | grep "<TASK_ID>" 命中 ≥ 1 行 |
| 4. wire-level 真命令 | producer 自报 "11/11 PASS" | pytest 真跑返 "11 passed in X.XXs" |

## 5. W12+ verify_prompt 必带行 (修整强制约束)

每个 plan_yaml task 的 verify_prompt 末尾必加:
```yaml
verify_prompt_extras: |
  Run D-VERIFY-RUNNER before accept:
    bash tools/d-verify-runner.sh <TASK_ID> <SCREENSHOTS_DIR> <DELIVERABLE_PATH> <WORKLOG_PATH>
  任何 1 步 FAIL → 整体 FAIL, override_accept 必须 wired 4 必查全 PASS 数字。
```

## 6. 修整 5+1 累计记录

| 次数 | 时间 | 漏查项 | 修整动作 |
|------|------|--------|----------|
| 1 | W6b 17:54 | deliverable.md | Step 2 必跑, 不靠印象 |
| 2 | W8 21:49 | A_WORKLOG.md | Step 3 必跑, grep 实证 |
| 3 | W9 22:53 | screenshots sha256 | Step 1 必跑, sha256sum 真命令 |
| 4 | W9 23:10 | pytest 缺 1 case | Step 4 必跑, pytest 真输出 |
| 5 | W10 23:55 | output/B-W10-4 段位错 | Step 2 逐段读, 不光看存在 |
| 6 | W11-2 | (修整前) 修整 #1-#3 | 本文件 + tools/d-verify-runner.sh (C-W11-3) |

---

**修整 #1 完成判定**: W12+ D verifier 跑 D-VERIFY-RUNNER 4 必查全 PASS, 0 漏查。
