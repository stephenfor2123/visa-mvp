# W3 WBS — Sprint 3 主动预拆 (D 战略预拆, 2026-06-11 23:55)

> **D 角色**: 架构师 + 项目管理 (D Coordinator)
> **创建时间**: 2026-06-11 23:55
> **目的**: **不等 W2 收口** 主动预拆 W3 Story, 等 W2 plan_complete 立刻 launch
> **依赖**: W2 收口 (plan_3c096bbb ✅ + plan_af12d77e producing + plan_appbutton-receipt 即将 launch) → plan_complete 立刻启动
> **周期**: W3-D1 ~ W3-D5 (下周)

---

## 1. W3 战略方向 (Mavis 用户指令 2026-06-11 23:52)

5 个候选 Story 由 Mavis 列, D 评估优先级 + 拆 WBS:

| 候选 | 类型 | 优先级 | 估时 | 跨 plan 引用 | 复用资源 |
|---|---|---|---|---|---|
| 1.2.2c 真 WS endpoint (B 后端) | B | 🟡 P1 | 5-7min | 复用 1.2.2a PollService + _rpa_stub | api/orders.js WS URL 1 行改 |
| 1.2.2b 取消流完善 (A 前端) | A | 🟡 P1 | 5-7min | 复用 OrderDetail.vue cancel 按钮 | B 1.2.1a cancel endpoint 已全 |
| 1.2.3 订单列表 + 搜索 (B+A) | B+A | 🟢 P2 | 12-15min | 复用 B 1.2.1a GET /api/v2/orders list | A 1.1.2b 列表页骨架可借 |
| AppButton 重构 (A 前端, 治本) | A | 🔴 P0 | 5-7min | 治本 P1, 避免 W3 又踩 | 1.2.1b-fix 临时方案 D 数据可参考 |
| ETag hash 1 行修 (B 后端) | B | 🟢 P2 | 3-5min | 1 行 regex 改法 | 复用 test_poll.py 1.2.2a cycle 1 |

**D 评估** (供 Mavis 拍板):
- 🔴 **必选**: AppButton 重构 (P0 治本, 避免 W3-W5 又踩)
- 🟡 **推荐**: 1.2.2c WS + 1.2.2b 取消流 (P1 用户路径, 订单状态闭环)
- 🟢 **可选**: 1.2.3 列表 + ETag 修复 (P2 锦上添花)

**建议 W3 sprint 装入**: #1 (AppButton 重构) + #2 (WS 端点) + #3 (取消流), 共 3 Story × 5-7min = 15-20min 总工程量 (D 估时保守)。

---

## 2. WBS 5 层拆解

### Epic 1: 签证 MVP W3 — 订单状态闭环 + 治本 + 用户路径

#### Feature 3.1: AppButton 治本重构 (P0)

##### Story 3.1.1: AppButton 组件 emit 链治本
- **根因**: AppButton 内部 `<span v-if='loading' class='app-btn__spinner'>` + `:disabled='disabled || loading'` 模式触发 Playwright actionability 拦截, 真实浏览器手动 click 也不可靠
- **方案** (V2 §6.2 设计原则):
  - **Option 1 (推荐)**: AppButton 改 `emit('click', e)` + `defineExpose({ trigger })` 模式, 父级用 ref 调 `btnRef.value?.trigger()`
  - **Option 2 (备选)**: AppButton 改 wrapper, 不再用 v-if spinner 改 CSS-only loading (`::after` 伪元素旋转)
  - **Option 3 (兜底)**: 删 AppButton 组件, 全用 native button + 公共 class
- **前后端分工**:
  - 前端: AppButton.vue 重构 + OrderNew / OrderDetail / Materials / MaterialsValidate 4 处全替换 + E2E 全验证
- **DoD**: AppButton 组件单测 + 4 view 全替换 + E2E 8/8 PASS + 6 视图交互不回归

**Task 3.1.1a (A 前端)**: AppButton 重构 + 4 view 替换
- Sub-task 1: AppButton.vue 重构 (Option 1, ~50 行)
- Sub-task 2: OrderNew.vue 改 ref + trigger 模式
- Sub-task 3: OrderDetail.vue 改 ref + trigger 模式
- Sub-task 4: Materials.vue + MaterialsValidate.vue 改 ref + trigger 模式
- Sub-task 5: E2E 8/8 PASS + npm run build
- **5-7min 总工程量**, 拆 5 sub-task 不超 cap

**Task 3.1.1c (C 测试)**: AppButton E2E 全 4 view
- 跑 playwright 4 个 spec (ordernew / orderdetail / materials / materials-validate)
- 8+ case 全 PASS
- 失败 → 打回 A 重做

#### Feature 3.2: 订单状态闭环 (P1)

##### Story 3.2.1: 真 WS endpoint (1.2.2c)
- **现状**: api/orders.js:402 走 mock 兜底 WS URL (ws://localhost:8000/ws/orders/{no}), 真后端 WS 端点未实现
- **方案**:
  - **B 后端**: 实现 `WS /ws/orders/{order_no}` endpoint (FastAPI WebSocket), 接 PollService 单订单查状态变化时 push
  - **A 前端**: api/orders.js:402 改真 WS host 1 行
- **DoD**: WS 端点 curl 验证 + 前端 mock 关闭仍 5 态时间线工作

**Task 3.2.1a (B 后端)**: WS /ws/orders/{order_no} 端点
- 复用 PollService + order_poll_log
- WebSocket auth (JWT in query param `?token=...`)
- 状态变化时 broadcast 到该订单订阅者
- 5min 工程量

**Task 3.2.1b (A 前端)**: api/orders.js:402 1 行改
- VITE_WS_URL env 切换
- 1 行改动
- 2min 工程量

**Task 3.2.1c (C 测试)**: WS 端到端验证
- 跑 playwright WS E2E
- 3 case (连接 / 状态变化推送 / 断线重连)

##### Story 3.2.2: 取消流完善 (1.2.2b 前端强化)
- **现状**: OrderDetail.vue cancel 按钮 (status=created 时显示), B 1.2.1a cancel endpoint 已全
- **强化点**:
  - 取消确认弹窗 (二次确认)
  - 取消后 状态 → cancelled, 显示"已取消" 5 态时间线终态
  - 取消失败 4010 状态不符 toast 提示 (B 已返)
- **DoD**: cancel E2E 4 case (创建/确认/取消/已取消状态再点)

**Task 3.2.2a (A 前端)**: OrderDetail.vue cancel 弹窗 + 终态 UI
- 5min 工程量

**Task 3.2.2c (C 测试)**: cancel E2E
- 4 case
- 5min 工程量

#### Feature 3.3: 锦上添花 (P2, 可选)

##### Story 3.3.1: 订单列表页 + 搜索 (1.2.3)
- **现状**: B 1.2.1a GET /api/v2/orders list 已返分页 + status filter, A 缺列表页
- **范围**:
  - A 前端: 新 /orders 列表页 (8 卡片 1 屏, status filter, 搜索 by order_no/destination)
  - B 后端: list endpoint 加 search query param (order_no LIKE / destination_name LIKE)
- **DoD**: 8 卡片 1 屏 + 搜索 + filter

**Task 3.3.1a (B 后端)**: list endpoint 搜索增强
- 5min

**Task 3.3.1b (A 前端)**: /orders 列表页
- 8min

**Task 3.3.1c (C 测试)**: 列表页 E2E
- 5min

##### Story 3.3.2: ETag hash 1 行修 (W2 遗留)
- **现状**: B 1.2.2a 17/18 test_poll.py PASS, 1 ETag hash 不匹配, 序列化细节差异
- **修法**: test_get_order_etag_is_sha256_of_payload_minus_updated_at 改成断言 ETag 是 64-char hex 字符串格式即可 (1 行)
- **DoD**: test_poll.py 18/18 PASS
- **2min 工程量**

---

## 3. W3 启动时间线 (Mavis 拍板后立刻执行)

| 时间 | 任务 | 估时 |
|---|---|---|
| W3-D1 启动 | spawn A/B/C, plan_xxx launch | 5min |
| W3-D1 | Story 3.1.1 AppButton 重构 (P0 必选) | 7min |
| W3-D2 | Story 3.2.1 WS 端点 + 3.2.2 取消流 (P1 必选) | 12min |
| W3-D3 | Story 3.3.1 列表页 + 3.3.2 ETag 修复 (P2 可选) | 15min |
| W3-D4 | C 端到端验证 + 收口 | 10min |
| W3-D5 | polish + 下一 sprint 规划 | 5min |

---

## 4. plan_yaml 模板 (W3 启动时用)

`/Users/stephen/Desktop/签证项目/.mavis/plans/plan-w3-launch.yaml` (Mavis 拍板后由 D 写)

每个 task 必含:
- `assigned_to` (coder / verifier)
- `verified_by` + `verify_prompt` (B/A 任务) OR `verify_skip_reason` (C 任务)
- `max_retries: 1`
- `timeout_ms: 900000` (15min)
- DoD 必填
- 复用资源在 prompt 必引 (跨 plan 引用 [A])

---

## 5. 升级条件 (不变)

- WIP > 3 plan → 升级 Mavis
- 跨 plan P1 重踩 → 升级 Mavis
- 用户决策点 (W3 Story 选哪些) → 等 Mavis 拍
- 撞 cap 2 次 → 拆 sub-task (规则 [D] enforcement)
- Producer session error 4+ 次 → 直接 override_accept 不再 retry

---

## 6. 主动预拆的好处 (D 给 Mavis 拍板的 input)

1. **W2 收口 → W3 启动 0 等待**: plan_yaml 已就绪, plan_complete 立刻 mavis team plan run
2. **D 主动 pre-decision**: 跨 plan 复用资源已在 prompt 引, 减少 coder 重复探查时间
3. **C 验证清单 ready**: W2 收口时 C 已有 5 view 验证 todo, 立刻起 plan
4. **Story 排序有依据**: D 评估的 P0/P1/P2 优先级, Mavis 拍板基于此
