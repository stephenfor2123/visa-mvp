# MVP Launch Checklist — 签证项目

> **MVP 定义**:能跑通核心用户流程（注册 → 申请 → OCR 识别 → 支付 mock → 状态查询）即可视为 MVP 达标。
> 本清单是验收前必须勾选完毕的 6 大块 22 项检查项,**所有项初始状态均为"待验证"**,由 Sprint 团队按 S0–S6 顺序逐项打勾。

---

## 项目结构速查

| 模块 | 路径 | 关键技术栈 |
|---|---|---|
| Web 端 | `frontend/web/` | Vue 3 + Vite + Element Plus + Pinia |
| iOS 端 | `frontend/ios/` | Flutter 3.19+ / Dart 3.3+ |
| 后端 | `backend/` | FastAPI 0.115 + SQLAlchemy 2 + Alembic + Celery |
| 文档 | `docs/` + 根目录 `*.md` | Markdown |
| 监控/脚本 | `backend/scripts/` | backup.py / restore.py |

---

## 0. 验收总览

| 大块 | 项数 | 通过 | 未通过 | 待验证 | 通过率 |
|---|---:|---:|---:|---:|---:|
| A. Web 端 | 10 | 0 | 0 | 10 | 0% |
| B. iOS 端 | 4 | 0 | 0 | 4 | 0% |
| C. 后端 | 2 | 0 | 0 | 2 | 0% |
| D. 文档 | 3 | 0 | 0 | 3 | 0% |
| E. 监控 | 2 | 0 | 0 | 2 | 0% |
| F. 安全 | 2 | 0 | 0 | 2 | 0% |
| **合计** | **23** | **0** | **0** | **23** | **0%** |

**MVP 准入门槛**:全部 23 项 ✅ 通过(无 ❌ 无 ⏳),且 S0–S6 顺序勾选不可跳级。

---

## A. Web 端(10 项)

> 工作目录:`frontend/web/`
> 启动命令:`npm install && npm run dev` (默认 http://localhost:5173)

| ID | 验收项 | 验证命令 / 步骤 | 状态 | 负责人 | 备注 |
|---|---|---|---|---|---|
| A·B1 | `npm run dev` 起服务无报错 | `cd frontend/web && npm run dev`;30s 内监听 :5173 | ⏳ 待验证 | | vite/element-plus 树摇可能在 macOS M1 挂起,见 W15-P0-3 |
| A·B2 | 首页能打开并显示 Hero + 4 国别 chip | 浏览器访问 `/`;首屏 SSR/CSR OK | ⏳ 待验证 | | 路由 `frontend/web/src/router/index.js` |
| A·B3 | 注册流程可走通 (邮箱/手机号 + 验证码) | 提交注册 → 收到 200 → 自动登录 | ⏳ 待验证 | | |
| A·B4 | 登录后 JWT 写入 + 受保护路由可访问 | 登录后访问 `/dashboard` 不重定向 | ⏳ 待验证 | | |
| A·B5 | 申请表单 (国家/签证类型/出行日期/个人信息) 可提交 | 填表 → submit → 200 + order_id | ⏳ 待验证 | | `frontend/web/src/views/OrderNew.vue` |
| A·B6 | 材料上传 (PDF/JPG/PNG, ≤10MB) 可成功 | 上传 1 个样本文件 → 返回 file_id | ⏳ 待验证 | | |
| A·B7 | OCR 触发并返回结构化字段 | 上传后 30s 内返回姓名/护照号/MRZ | ⏳ 待验证 | | mock OCR 已接通(W12 任务) |
| A·B8 | mock 支付按钮跳转 → 回调 → 订单变 paid | 点击 mock-pay → 跳转结果页显示绿色 ✓ | ⏳ 待验证 | | `frontend/web/src/views/PaymentResult.vue` |
| A·B9 | 状态查询页 (订单列表 + 详情) 正常 | 列表展示 5+ 订单,详情显示状态时间线 | ⏳ 待验证 | | |
| A·B10 | 后台管理登录 (admin/admin123) 可进入 dashboard | 登录 → `/admin/dashboard` 显示 KPI 卡片 | ⏳ 待验证 | | |

---

## B. iOS 端(4 项)

> 工作目录:`frontend/ios/`
> 构建命令:`flutter build ios --no-codesign --release`

| ID | 验收项 | 验证命令 / 步骤 | 状态 | 负责人 | 备注 |
|---|---|---|---|---|---|
| B·C1 | `flutter build ios --no-codesign` 编译成功 (无 Dart error) | 产物 `build/ios/iphonesimulator/Runner.app` 存在 | ⏳ 待验证 | | 需要 Xcode 15+ |
| B·C2 | 导出 `.ipa` (Archive) | `flutter build ipa --no-codesign` 或 Xcode → Archive | ⏳ 待验证 | | 产物 `build/ios/ipa/*.ipa` |
| B·C3 | 真机/模拟器安装成功并启动 | 拖入 Xcode Devices 或 `xcrun simctl install booted *.app` | ⏳ 待验证 | | |
| B·C4 | 核心流程跑通 (注册/登录/申请列表) | 模拟器手动走通 3 步 | ⏳ 待验证 | | |

> **注**:若 iOS 构建机不可用 (无 macOS + Xcode),该项可标记 ⚠️ N/A 并提供 `flutter analyze` 输出 + 模拟器截图作为替代证据。

---

## C. 后端(2 项)

> 工作目录:`backend/`
> 测试命令:`pytest -q --collect-only`(先确保可收集)→ `pytest -q`

| ID | 验收项 | 验证命令 / 步骤 | 状态 | 负责人 | 备注 |
|---|---|---|---|---|---|
| C·D1 | `pytest --collect-only` 全部可收集(0 collection error) | 修复 conftest.py 顺序 / 缺依赖 (W14-2 已记录 6 个 collection error) | ⏳ 待验证 | | 见 W14-2 postmortem |
| C·D2 | `pytest` 至少 **100+** test passed(无 critical 失败) | 跳过 `xfail`/`skip` 后 passed ≥ 100 | ⏳ 待验证 | | |

---

## D. 文档(3 项)

| ID | 验收项 | 验证命令 / 步骤 | 状态 | 负责人 | 备注 |
|---|---|---|---|---|---|
| D·E1 | `README.md`(根目录) 可达且含 quickstart | `cat README.md` 含 install / dev / test 三段 | ⏳ 待验证 | | |
| D·E2 | `CONTRIBUTING.md` 完整 (含 PR / 分支策略 / 编码规范) | 文件大小 > 5KB 且覆盖 git flow | ⏳ 待验证 | | 当前 16KB ✅ 大小达标 |
| D·E3 | `docs/API.md` 文档可达且与实际 endpoint 一致 | 抽查 3 个 endpoint 路径匹配 | ⏳ 待验证 | | 当前 23KB ✅ |

---

## E. 监控(2 项)

| ID | 验收项 | 验证命令 / 步骤 | 状态 | 负责人 | 备注 |
|---|---|---|---|---|---|
| E·F1 | `/health` 端点返回 200 + `{"status":"ok"}` | `curl http://localhost:8000/health` | ⏳ 待验证 | | `app/main.py:130` 已实现 |
| E·F2 | `backend/scripts/backup.py` 可执行并产生 sqlite/sql dump | `python backend/scripts/backup.py --out /tmp/backup` | ⏳ 待验证 | | |

---

## F. 安全(2 项)

| ID | 验收项 | 验证命令 / 步骤 | 状态 | 负责人 | 备注 |
|---|---|---|---|---|---|
| F·G1 | OWASP Top 3 高危已修(SQLi / XSS / IDOR) | 走 3 个攻击向量验证;在 SECURITY.md 标注修复 commit | ⏳ 待验证 | | |
| F·G2 | `SECURITY.md` 含漏洞报告邮箱/SLA | 文件大小 > 5KB | ⏳ 待验证 | | 当前 11KB ✅ 大小达标 |

---

## 验收流转规则

1. **顺序不可跳级**:S0 → S1 → ... → S6,前一块全部 ✅ 才能进入下一块。
2. **发现 ❌** → 立即开 issue,标记 `mvp-blocker` label,owner 24h 内修复并复测。
3. **发现 ⏳** → 每周 standup 同步进度,连续 2 周仍 ⏳ 自动升级为 P0。
4. **跨 sprint 教训**(W14-2):`tests/conftest.py` 缺依赖会一次性报 50+ failed,先跑 `--collect-only` 隔离 collection error。
5. **macOS M1 build hang**(W15-P0-3):vite build 可能静默挂起,优先走 `preview/*.html` + Chrome --headless fallback。

---

## 变更记录

| 日期 | 变更 | 作者 |
|---|---|---|
| 2026-06-15 | 初版 23 项清单,初始全 ⏳ | coder (sprint 16) |
