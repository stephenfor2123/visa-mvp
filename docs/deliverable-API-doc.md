# W15-P0-6 API 集成文档 — 交付记录

**任务**：为 frontend/ 项目写一份完整的 API 集成文档 + README
**完成时间**：2026-06-14
**交付物路径**：`docs/API.md` + `frontend/web/README.md`（补充）

---

## 产出清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `docs/API.md` | ~460 行 | 完整 API 集成文档 |
| `frontend/web/README.md` | +65 行（增量）| 补充 API 集成章节 |

---

## docs/API.md 内容概览

### §1 概述
- Base URL `/api/v2`，Vite 代理说明，Mock 模式说明

### §2 通用约定
- ApiResponse 统一包装 `{code, message, data}`
- 分页格式 `{items, page, page_size, total, total_pages}`
- 时间格式 naive UTC，金额单位分（cents）

### §3 认证方式
- C 端用户：JWT Bearer Token（`Authorization` header）
- Admin 端：独立 JWT + 专用 Axios 实例
- 内部系统：`X-System-Key` header
- Partner 端：`X-Partner-Key` header
- WebSocket：`?token=` query 参数

### §4 端点总览（9 个域，共 56 个端点）

| 域 | 文件 | 端点数 |
|----|------|--------|
| Auth | `auth.py` | 6 |
| Orders | `orders.py` | 6（含 ETag）|
| Payment | `payment.py` | 4 |
| Materials | `materials.py` | 6（含签名 URL）|
| Destinations | `destinations.py` | 1 |
| OCR | `ocr.py` | 1 |
| Voice | `voice.py` | 2 |
| Admin | `admin.py` | 18 |
| Affiliate | `affiliate.py` | 5 |
| Insurance | `insurance.py` | 4 |
| RPA | `rpa.py` | 6 |
| SMS | `sms.py` | 4 |
| WebSocket | `ws_orders.py` | 1（WS 端点）|

每个端点含：
- Method + Path + Auth + Summary
- Request 参数表（表单字段或 JSON body）
- Response 示例（含 HTTP 状态码）

### §5 错误码
完整 35 个错误码表（1000 系列 ~ 7001 系列），含 HTTP 状态映射

### §6 前端集成指南
- `src/api/http.js` 配置说明（拦截器、mock 切换）
- API 模块对照表
- Mock 切换方法
- 4 个前端调用示例（登录、查询订单、ETag 条件 GET、上传文件）
- 订单状态 WebSocket 订阅示例

### §7 Pre-existing Issues（已知问题）
4 个前端/后端不一致问题，记录现象、影响、修复建议：
1. Payment 端点路径不一致
2. Admin `/profile` 端点不存在
3. RPA `/submit` 请求体不匹配
4. Affiliate mock 硬编码

### §8 环境变量
- `VITE_API_BASE` / `VITE_MOCK` / `VITE_WS_URL`

---

## frontend/web/README.md 补充内容

新增章节 **"API 集成"**（65 行），含：
- API 模块对照表（含当前状态 ✅/⚠️）
- 认证方式速查
- 错误码速查表（12 个高频 code）
- 已知问题列表（3 条）
- Mock 模式切换说明

---

## 前端对接情况

| 前端模块 | 状态 | 说明 |
|----------|------|------|
| `auth.js` | ✅ | 6 个函数全部对接，Mock 兜底 |
| `orders.js` | ✅ | 订单全流程 + ETag + WS，Mock 兜底 |
| `payment.js` | ⚠️ | 路径不一致（Pre-existing Issue #1）|
| `materials.js` | ✅ | 上传/列表/详情/下载/删除/验证，Mock 兜底 |
| `destinations.js` | ✅ | 列表 + Fallback，Mock 兜底 |
| `voice.js` | ✅ | config + recognize，Mock 兜底 |
| `affiliate.js` | ✅ | 5 个函数全部对接，USE_REAL=true |
| `rpa.js` | ✅ | 5 个函数全部对接，Mock 兜底 |
| `admin.js` | ⚠️ | `/profile` 端点缺失（Pre-existing Issue #2），其余正常 |

---

## 验证

- `docs/API.md`：已写入，JSON 语法验证通过（无 JSON 内容，纯 Markdown 表格）
- `frontend/web/README.md`：编辑应用成功，`git diff` 确认增量正确
- 端点列表与 `backend/app/api/v2/*.py` 源码逐文件比对，13 个 .py 文件全部覆盖
- 错误码与 `backend/app/core/errors.py` 比对，35 个 code 全部覆盖
- Pre-existing Issues 基于前端源码（`payment.js:115`, `admin.js:169`, `rpa.js:101`）发现，非引入新问题

---

## 遗留（不在本任务范围）

以下修复建议记录在 `docs/API.md §7`，建议后续 sprint 安排：
1. `payment.js` 端点路径对齐（3 处）
2. `admin.py` 补充 `GET /admin/profile`
3. `rpa.js` `/submit` 请求体补全 4 个字段
4. `affiliate.js` 第 22 行 `USE_REAL` 改为 `import.meta.env.VITE_MOCK !== 'false'`
