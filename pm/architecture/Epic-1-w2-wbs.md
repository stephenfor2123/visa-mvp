# Epic 1: 美国签证 MVP W2 — 端到端申请流程

> **D 角色**:架构师 + 项目管理(D session archived, Mavis 代笔)
> **创建时间**: 2026-06-11 20:10
> **依赖**: W1 收口(8/8 E2E) 已完成(由 C agent 验证)
> **周期**: W2-D1 ~ W2-D5(本周)

---

## 1. 架构设计 (W2 范围)

**采用模式**: 前后端分离 + 单一 FastAPI 后端 + 共享 SQLite(开发) / 未来切 PostgreSQL(生产)

**不引入微服务** (V2 阶段) — 单体 FastAPI + 模块化 router,7 大服务在 1 个进程内通过 APIRouter 拆分。理由:
- W2 阶段单团队 5 人,微服务运维成本远大于收益
- 出问题定位困难(服务间 trace)
- 后期可拆:每个 router 已经是独立模块,平移即可

**技术栈 (W2 不变)**:
- 后端: FastAPI 0.115+ SQLAlchemy 2.0 async + Pydantic v2 + Alembic + Celery + Redis
- 前端: Vue 3 + Vite + Element Plus + Pinia + vue-router + vue-i18n
- OCR: PaddleOCR 2.7+ (本地 CPU 推理)
- 语音: FunASR paraformer (本地)
- RPA: Playwright + Camoufox + ddddocr
- 测试: pytest + httpx + Playwright (前端) + Locust (压测)
- 部署: Docker Compose (本地) + ngrok (临时域名)

---

## 2. WBS 5 层拆解

### Epic 1: 美国签证 MVP W2 — 端到端申请流程

#### Feature 1.1: 材料采集 (W2 核心)

##### Story 1.1.1: 材料上传端到端
- **前后端分工**: 
  - 后端: 文件上传/下载/缩略图/OCR 异步任务/同文件去重
  - 前端: 扫描引导页(N1)/材料列表/拍照+PDF+语音 3 入口
- **Definition of Done**: 用户能上传护照图片,后端 OCR 异步识别,前端展示 OCR 进度和结果

**Task 1.1.1a (B 后端)**: 文件服务 - 上传/下载/缩略图
- 端点: `POST /api/v2/materials/upload` (multipart)
- 端点: `GET /api/v2/materials/{id}` (详情含 OCR 结果)
- 端点: `GET /api/v2/materials/{id}/download` (5min 签名 URL)
- 端点: `DELETE /api/v2/materials/{id}` (软删)
- 模型: `Material` (B 已有骨架,补字段)
- 缩略图: Pillow 800x800
- 加密: AES-256-GCM
- **Sub-task 自主拆**: 5-8 个

**Task 1.1.1b (A 前端)**: 扫描页 + 材料列表
- 页面: `/materials` (登录后)
- 页面: `/materials/scan` (扫描引导 N1)
- 组件: 拍照/PDF/语音 3 入口
- i18n: `materials.*` keys
- **Sub-task 自主拆**: 5-8 个

**Task 1.1.1c (C 测试)**: 上传 E2E
- 跑 `pytest tests/integration/test_materials.py` (5+ cases)
- 跑 Playwright 上传流程
- 失败 → 打回 B/A (记录原因)

##### Story 1.1.2: AI 校验 15+ 规则端到端
- 端点: `POST /api/v2/materials/validate`
- 规则引擎: 可视化配置 + 15+ 规则 JSON
- 前端: 校验结果页 N2 (绿/黄/红三档)
- **Task 1.1.2a (B)**: AI 校验引擎实现
- **Task 1.1.2b (A)**: 校验结果页
- **Task 1.1.2c (C)**: 校验 E2E

#### Feature 1.2: 表单填写与订单创建 (W2 中)

##### Story 1.2.1: 表单填写端到端
- 前端: 表单页 (OCR 预填 + 手动编辑)
- 后端: 订单创建端点
- **Task 1.2.1a (B)**: 订单创建 + 材料关联
- **Task 1.2.1b (A)**: 表单填写页
- **Task 1.2.1c (C)**: 订单创建 E2E

##### Story 1.2.2: 订单状态详情
- 前端: 订单状态详情页 N4 (5 态时间线)
- 后端: 状态轮询任务 (Celery)
- **Task 1.2.2a (B)**: 状态轮询 + 状态机
- **Task 1.2.2b (A)**: 订单状态详情页
- **Task 1.2.2c (C)**: 状态查询 E2E

#### Feature 1.3: RPA 美国签证 (W2 高风险 PoC)

##### Story 1.3.1: RPA 框架 PoC
- 后端: Playwright + Camoufox + ddddocr 跑通
- **决策门**: 跑通 → 推进 Story 1.3.2; 跑不通 → 降级"半自动" (App 端引导用户填, RPA 只做提交)
- **Task 1.3.1a (B)**: RPA 框架搭建 + 美国 DS-160 PoC
- **Task 1.3.1b (C)**: RPA 集成测试 (用 mock DS-160)

---

## 3. W2 节奏 (5 天 / 10 分钟 mini-sprint)

| 天 | 任务组合 | D 复盘 (10 min) | 关键里程碑 |
|---|---|---|---|
| W2-D1 | B 1.1.1a + A 1.1.1b 并行 | 10min 一次, 看 B/A 任务量 | 提交 → C 测 |
| W2-D2 | C 测 1.1.1 + B 1.1.2a + A 1.1.2b | 同上 | 校验规则 PASS |
| W2-D3 | C 测 1.1.2 + B 1.2.1a + A 1.2.1b | 同上 | 订单创建 PASS |
| W2-D4 | C 测 1.2.1 + B 1.2.2a + A 1.2.2b | 同上 | 状态查询 PASS |
| W2-D5 | C 测 1.2.2 + B 1.3.1a RPA PoC | 同上 | W2 收口 + RPA 决策 |

---

## 4. D 复盘规则 (10 分钟一次)

D 每 10 分钟读所有 agent 的 WORKLOG,聚合写到 `pm/sprint/{HH-mm}.md`:

```bash
# 伪代码
for agent in [A, B, C]:
    read_worklog(agent)
    in_progress_count = count_in_progress(agent)
    if in_progress_count > 6:
        request_more_agents(agent)  # 通知 Mavis
    if in_progress_count < 2:
        # 任务可合并,等下一波
        pass
```

**Mavis 决定 spawn 新 A' / B' 的标准**:
- 1 个 A 撑 6 个 Sub-task
- 当前 1 个 A 已有 6+ 在跑 → spawn A' (新 session, 读 DASHBOARD + A_WORKLOG 起步)
- 当前 1 个 A 只有 2-3 在跑 → 任务可合并, 不加

---

## 5. C 打回规则

C 测试失败:
- 写原因到 `qa/feedback/{story}-{round}.md`
- 通知 A/B(用 mavis communication send 或 DASHBOARD flag)
- A/B 修 → 重测

**3 次打回后卡死**:
- C 自动通知 Mavis
- Mavis 介入: 看历史 → 决定重拆 Sub-task / 拆 Story / 升级 owner

---

## 6. W2 完成 Definition of Done

- [ ] Feature 1.1 (材料 + 校验): 用户上传护照, OCR 异步完成, 15+ 校验规则全过
- [ ] Feature 1.2 (订单): 用户创建订单 + 看到状态详情
- [ ] Feature 1.3 (RPA): PoC 跑通 OR 降级半自动方案
- [ ] C 测: W2 全部 E2E PASS
- [ ] D 文档: pm/architecture/Epic-1-w2-wbs.md 完整
- [ ] A/B/C WORKLOG 持续更新

---

**D 协调者**: 等 C 收 W1 + A/B 接 W2 任务
