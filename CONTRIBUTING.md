# Contributing to Visa Helper (签证项目)

欢迎加入 **Visa Helper** 的开发!本文档面向所有贡献者,涵盖开发环境、Git workflow、commit 规范、本地启动、代码风格、PR 流程与测试要求。

> 仓库布局:`backend/`(FastAPI 服务) + `frontend/{web,ios,miniprogram}`(三端客户端)+ `docs/`(设计 & 协议文档)+ `pm/`(产品说明)+ `qa/`(质量验收)。

---

## 1. 开发环境要求

| 工具 | 版本 | 必装 / 可选 | 用途 |
|---|---|---|---|
| **Python** | **3.11+**(CI 用 3.11;`pyproject.toml` 标 `>=3.9`,本地建议 3.11) | 必装 | 后端运行时 + pytest |
| **Node.js** | **18+**(CI 用 20,本地 18 LTS / 20 LTS 都可) | 必装 | `frontend/web` + `frontend/miniprogram` 构建 |
| **Flutter** | **3.19+**(CI 锁 3.44.2,本机 ≥ 3.19 即可) | 必装 | `frontend/ios` 跨端 iOS App |
| **Xcode** | 15+(macOS only) | 可选 | iOS 真机/模拟器运行 `frontend/ios` |
| **Docker + Docker Compose** | v2+ | 可选 | 跑 `backend/docker-compose.yml`(Postgres + Redis + API) |
| **PostgreSQL** | 16+(若不走 Docker) | 可选 | CI 测试用 `postgres:16-alpine` |
| **Git** | 2.30+ | 必装 | 全部版本控制 |
| **make** / **bash** | — | 必装 | 执行脚本 |

> **平台注意**:Flutter iOS 端需在 macOS 上 build & run。Windows / Linux 只能跑 `flutter analyze` + `flutter test`,不能 build iOS bundle。

### 一次性环境校验

```bash
python3 --version        # >= 3.11
node --version           # >= 18
npm --version
flutter --version        # >= 3.19
git --version
docker --version         # optional
```

---

## 2. Git Workflow

### 2.1 分支模型(Git Flow 轻量化)

```
main                 ← 稳定 / 已发布,tag 在此打,只接受 merge from develop / hotfix
 │
develop              ← 日常集成分支,所有 feature/* 汇入此处
 ├── feature/<scope>  ← 功能分支(从 develop 切,merge 回 develop)
 │     例:feature/auth-2fa、feature/payment-stripe
 ├── release/<ver>    ← 发版准备(从 develop 切,merge 回 main + develop)
 └── hotfix/<scope>   ← 紧急修复(从 main 切,merge 回 main + develop)
       例:hotfix/login-token-leak
```

**当前状态**:仓库只有 `main` 分支(初始交付)。首次多人协作时,先由项目负责人创建 `develop` 并 push:

```bash
git checkout -b develop
git push -u origin develop
```

> **CI 当前配置** (`.github/workflows/ci.yml`):`push main` 与 `pull_request main` 触发四个 job(backend pytest / frontend playwright / flutter analyze / miniprogram build)。后续接入 `develop` 时,把 workflow 里的 `branches: [main]` 同步追加 `develop`。

### 2.2 分支命名

| 类型 | 模式 | 示例 |
|---|---|---|
| Feature | `feature/<scope>-<short-desc>` | `feature/auth-2fa`、`feature/admin-rate-limit` |
| Hotfix | `hotfix/<short-desc>` | `hotfix/login-token-leak` |
| Release | `release/<semver>` | `release/v0.2.0` |
| Spike / 调研 | `spike/<topic>` | `spike/ocr-paddle-eval` |

`<scope>` 建议与 `frontend/web` / `backend` / `docs` / `pm` 等子目录名对齐,便于从分支一眼看出影响面。

### 2.3 日常流程

```bash
# 1) 拉最新 develop
git checkout develop && git pull --rebase

# 2) 切功能分支
git checkout -b feature/auth-2fa

# 3) 开发 + 频繁 commit(参见 §3)
...

# 4) 推送前自检
make test      # 或手动跑: backend pytest + frontend lint/build

# 5) push + 开 PR
git push -u origin feature/auth-2fa
gh pr create --base develop --title "feat(auth): add 2FA TOTP" --body "..."
```

---

## 3. Commit 规范(Conventional Commits)

### 3.1 格式

```
<type>(<scope>): <subject>

<body>(可选,72 字符换行)

<footer>(可选,关联 issue / breaking change)
```

### 3.2 type 清单

| type | 用途 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat(auth): add TOTP 2FA login flow` |
| `fix` | bug 修复 | `fix(payment): prevent double-charge on Stripe retry` |
| `chore` | 构建/工具/依赖(不直接影响产品) | `chore(deps): bump fastapi to 0.115.6` |
| `docs` | 文档(代码注释除外) | `docs(legal): add protocol review notes for zh-CN/en` |
| `style` | 格式(空格/分号/引号),不改变逻辑 | `style(web): run prettier on views/*` |
| `refactor` | 重构(非新功能、非修 bug) | `refactor(db): split user repository into per-domain files` |
| `test` | 测试相关 | `test(rpa): add captcha solver unit tests` |
| `perf` | 性能优化 | `perf(api): cache destination list with 60s TTL` |
| `ci` | CI 配置 | `ci(github): add bundle-size check on frontend build` |
| `revert` | 回滚 | `revert: feat(payment) stripe v2 — rollback pending legal review` |

### 3.3 写作规则

- **subject** 用祈使句、小写开头、不加句号,≤ 50 字符:`add login` 而非 `Added login` / `adds login`。
- **scope** 与改动主目录对齐(`auth` / `payment` / `web` / `miniprogram` / `ios` / `ci` 等)。
- **body** 回答 *为什么*(why)而不只是 *做了什么*(what);列要点用 `-`。
- **footer** 用 `Refs: #123` / `Closes: #123` / `BREAKING CHANGE: <desc>`。
- 单次 commit 聚焦一个意图,不要把 `feat + fix + chore` 混在一起。

### 3.4 示例

```
feat(auth): add SMS rate-limit (5/min per phone)

- add 2010 SMS_RATE_LIMIT error code (V2 §9.3)
- count attempts in Redis with 60s sliding window
- return 429 with Retry-After header

Refs: #42
```

```
fix(payment): avoid double-charge on Stripe webhook retry

The provider webhook was re-processing events whose id we had already
recorded. We now dedupe on `event_id` inside a UNIQUE index and
return 200 on duplicate replay.

BREAKING CHANGE: stripe webhook payload now requires `event.id`
```

---

## 4. 本地启动

### 4.1 Backend(`backend/`)

#### A. venv 模式(轻量,SQLite)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env       # 按需改 JWT_SECRET / STRIPE / SMS_*
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000

# 健康检查
curl http://localhost:8000/health
# => {"status":"ok","app":"Visa MVP API","version":"0.1.0"}
```

#### B. Docker Compose 模式(Postgres + Redis + API)

```bash
cd backend
cp .env.example .env       # 按需改
docker compose up --build

# 容器自动 alembic upgrade head;数据落 ./.data/,日志 ./.logs/
```

#### C. 测试模式 SMS

`.env` 中 `SMS_CHANNEL=mock` 时,**任意 6 位数字**验证码都通过(便于联调)。生产切换 `SMS_CHANNEL=twilio` 即用 Twilio adapter。

### 4.2 Frontend Web(`frontend/web`)

```bash
cd frontend/web
npm install
npm run dev               # http://localhost:5173
# 可选:
npm run build             # 生产构建到 dist/
npm run preview           # 预览 dist(端口 4173)
npm run test:e2e          # Playwright 端到端(需先启 backend)
```

### 4.3 Frontend iOS(`frontend/ios`,Flutter)

```bash
cd frontend/ios
flutter pub get
flutter run               # 选连接的设备/模拟器
# 可选:
flutter analyze           # 静态分析(CI 同款)
flutter test              # 单元 + widget 测试
```

### 4.4 Frontend Miniprogram(`frontend/miniprogram`)

```bash
cd frontend/miniprogram
npm install
npm run build:weapp        # 静态校验 + miniprogram-ci 尝试
npm run build:weapp:verbose # 含详细 report(build_report.json)
```

> 完整 e2e 联调需本地同时跑 backend (`:8000`) + frontend web (`:5173`)。CI 上 frontend job 用 stub API,不依赖 backend。

---

## 5. 代码风格

### 5.1 Python(`backend/`)

- **Formatter**: `black`(line-length 88) + `isort`(profile `black`)。
- **Linter**: `ruff`(替代 flake8/ pylint,速度快 10-100×),启 `E, F, W, I, B, UP` 规则集。
- **Type hints**: 全部 public function / method 必加(项目已用 SQLAlchemy 2.0 typing 模式);内部 helper 也鼓励。
- **命名**: 模块 `snake_case`;类 `PascalCase`;常量 `UPPER_SNAKE`;私有前缀 `_`。
- **Docstring**: 公开 API 用 Google 风格;复杂业务(支付/RPA)函数必须有 1 段说明意图 + 参数 + 返回值 + 异常。
- **错误码**: 后端统一使用 V2 §9.3 段位(`1xxx` 通用 / `2xxx` Auth / `3xxx` User / `7xxx` 第三方),新增时同步 `docs/API.md` 与 `app/core/errors.py`。
- **依赖**: 新增 import 必须出现在 `requirements.txt` 中(锁版本);冷依赖(可选)放 `[optional]` 块或单独 `requirements-<feature>.txt`。

#### 最小检查命令

```bash
cd backend
.venv/bin/pip install black isort ruff
.venv/bin/ruff check app/
.venv/bin/black --check app/
.venv/bin/isort --check-only app/
```

### 5.2 JavaScript / Vue(`frontend/web`,`frontend/miniprogram`)

- **Formatter**: `prettier`(单引号、无分号、printWidth 100、SFC indent 2)。
- **Linter**: `eslint`(`@vue/eslint-config-airbnb` 或团队选定 preset),Vue 模板 `eslint-plugin-vue`。
- **命名**:
  - 组件文件 `PascalCase.vue`(`PaymentResult.vue`)
  - composable / util `camelCase`(`useAuth.js`)
  - 路由 path `kebab-case`(`/payment/result`)
  - 常量 `UPPER_SNAKE`
- **Composition API** 优先;Options API 仅在历史页面保留。
- **i18n**: 新增用户可见字符串必须同时入 `frontend/shared/i18n/{zh-CN,en,id,vi}.json`,**禁止**硬编码中文/英文。多语种合规 placeholder 约定见 `docs/LEGAL_REVIEW_NOTES.md`。
- **依赖**: `npm install <pkg>` 后必须提交 `package.json` / `package-lock.json`。

#### 最小检查命令

```bash
cd frontend/web
npm run lint       # 若已配置
npx prettier --check "src/**/*.{vue,js,scss}"
```

> 注:W1 阶段 `npm run lint` 是 `echo 'lint skipped for W1'` 占位,W2 起必须接入 eslint + prettier 并移除此占位。

### 5.3 Dart / Flutter(`frontend/ios`)

- **Formatter**: `dart format`(随 Flutter SDK)。
- **Linter**: `flutter analyze`(使用 `frontend/ios/analysis_options.yaml` + `flutter_lints`)。
- **命名**: 类 `PascalCase`;文件 `snake_case.dart`;常量 `lowerCamelCase` (Dart 习惯)。
- **状态管理**: 沿用项目既定 `provider`(`pubspec.yaml` 已声明);新功能不要再引入 `riverpod` / `bloc`,除非团队讨论通过。

### 5.4 通用规范

- **Secrets**: 任何 `.env` / `*.pem` / `*.key` / `*.pfx` **绝不**入仓,CI / 本地均通过环境变量注入(参考 `.gitignore`)。
- **路径**: 所有 JS/Python import 优先相对或 `~/` 别名,避免深度相对(`../../../`)。
- **日志**: 后端用 `loguru`(已锁定);前端 console 仅在 `import.meta.env.DEV` 下输出;小程序同理。
- **错误处理**: 任何 try/except 必须显式处理,不允许 `except: pass` / 空 catch;前端 axios 拦截器统一走 `src/api/errorHandler.js`。
- **删除**: 删文件用 `mavis-trash` 或 `git rm`,禁止 `rm -rf` 操作项目内文件。

---

## 6. PR Review Checklist

**作者自检(开 PR 前必须勾选)**:

- [ ] PR 标题遵循 §3.1 Conventional Commits 格式
- [ ] `git rebase` 过 `develop`(无多余 merge commit / `fixup!`)
- [ ] `backend`: `pytest tests/ -m "not slow"` 全绿;新增测试覆盖改动点
- [ ] `frontend/web`: `npm run build` 通过;`npm run test:e2e` 相关 spec 全绿
- [ ] `frontend/ios`: `flutter analyze` 0 错(警告尽量清)
- [ ] `frontend/miniprogram`: `npm run build:weapp` 退出码 0
- [ ] 新增 / 修改的接口参数更新到 `docs/API.md`
- [ ] 新增用户可见文案同步到 `frontend/shared/i18n/*.json`(4 个语种)
- [ ] 数据库 schema 改动附 alembic 迁移文件;**禁止**手动编辑既有迁移
- [ ] 未引入 `console.log` / `print` 调试残留(生产代码)
- [ ] 未提交 `.env` / `*.bak` / `*.md~` / `node_modules` / `build/`
- [ ] CI 4 个 job(backend pytest / frontend playwright / flutter analyze / miniprogram build)全绿
- [ ] PR 描述包含:动机 / 改动点 / 截图(UI) / 关联 issue

**Reviewer 关注**:

- **设计**: 是否与 `docs/API.md` / `pm/*` 对齐;边界 / 错误码 / i18n 完整性
- **安全**: 鉴权 / 注入 / SSRF / 凭据泄露 / 越权
- **测试**: 是否覆盖 happy path + 边界 + 错误码
- **可观测性**: 关键路径是否打 log / 埋点
- **回滚**: 是否可以 feature flag / 灰度;迁移是否可逆
- **文档**: 公共 API / 配置项 / 错误码是否同步

> **Review SLA**: 工作日 24h 内 first response;非紧急 PR 48h 内 merge 或 close。

---

## 7. 测试要求

### 7.1 Backend — pytest(必跑)

```bash
cd backend
.venv/bin/pytest tests/ -m "not slow" --tb=short --maxfail=5 \
  --cov=app --cov-report=term-missing
```

- **必跑**:`tests/unit/`(纯函数 / service 层)+ `tests/integration/`(API + DB)。
- **慢测试**(OCR PaddleOCR warmup、真实 RPA)用 `@pytest.mark.slow` 标记,本地 + CI 默认 `not slow` 跳过。
- **覆盖率门槛**:新增 / 修改行 100% 覆盖;整体 ≥ 60%(V2 阶段目标)。
- **fixtures**: 共享 fixtures 放 `tests/conftest.py`;unit 专属放 `tests/unit/conftest.py`。
- **CI 跑 Postgres**: `.github/workflows/ci.yml` 用 `postgres:16-alpine` service container;本地默认 SQLite(`tests/conftest.py` 自动 `create_all`)。

### 7.2 Frontend Web — Playwright(必跑,关键路径)

```bash
cd frontend/web
npx playwright install --with-deps chromium   # 首次
npm run build
npm run test:e2e                              # 跑 e2e/ 下所有 spec
```

- 当前覆盖:destination / login / register / i18n-full-locale / screenshot 5 spec。
- **新增 E2E spec** 放 `frontend/web/tests/e2e/`,命名 `*.spec.js`。
- **截图** 用于视觉回归(spec 自动出 PNG 到 `playwright-report/`)。

### 7.3 Frontend iOS — flutter test

```bash
cd frontend/ios
flutter test --no-pub
```

- **必跑**:`frontend/ios/test/widget_test.dart` + 新增 widget / unit test。
- **CI 行为**:`continue-on-error: true`(避免历史 widget 报错阻塞);新提交需把相关 spec 修至通过。

### 7.4 Miniprogram — build_weapp.cjs 静态校验

```bash
cd frontend/miniprogram
npm run build:weapp:verbose
# 退出码 0 = BUILD_SUCCESS;非零 = FAIL
# 详细报告:build_report.json
```

- 不依赖微信开发者工具 CLI,只跑静态检查 + `miniprogram-ci` 尝试(失败也不阻塞)。

### 7.5 提 PR 前必跑

```bash
# 一键:
cd backend && .venv/bin/pytest tests/ -m "not slow" --tb=short
cd ../frontend/web && npm run build && npx playwright test --reporter=list
cd ../frontend/ios && flutter analyze --no-pub
cd ../frontend/miniprogram && npm run build:weapp
```

> **CI 是最终裁判**:本地通过 + CI 4 个 job 全绿 = 具备 merge 条件。

---

## 8. 其它约定

- **依赖升级**: `chore(deps):` 类型提交,PR 描述列升级前后影响;锁版本(不写 `^` 浮动到不兼容主版本)。
- **数据库迁移**: 一个 PR 一个迁移;迁移文件名 `alembic/versions/<rev>_<desc>.py`;**禁止**修改已合入主干的迁移。
- **配置**: 全部从 `app/core/config.py`(后端)/ `frontend/web/.env.*`(前端)读取;**禁止**硬编码连接串 / 密钥。
- **i18n & 法律**: 涉及多语种合规(隐私 / 服务条款 / 退款),遵循 `docs/LEGAL_REVIEW_NOTES.md` 三层 marker 流程,提交前标注 `__legal_review_pending__`。
- **文档先行**: 公共 API 改动先 PR `docs/API.md` 的 spec,再 PR 代码;评审以 spec 为准。
- **里程碑**: 沿用 `pm/W*.md` 中既定的 W-sprint 编号(如 `W14-9-legal-signing`、`W15-P0-bundle-optimization`);sprint 交付物放 `outputs/<sprint-id>/`。

---

## 9. 求助 / 反馈

- **仓库 Issues**: 提需求 / 报 bug;**安全相关 issue** 请按 `SECURITY.md`(若已发布)走私下渠道,**禁止**在 issue 里贴凭据 / 漏洞利用。
- **Slack / 飞书群**: 日常讨论(sprint 计划 / 阻塞 / 设计评审)。
- **On-call**: 见 `pm/contacts.md`(若有)。

---

## 10. License

提交 PR 即视为同意项目既定 License 的贡献者条款(参见根目录 `LICENSE`,若已发布)。无 License 文件时,默认 **All rights reserved**,外部贡献需先与维护者沟通授权。

---

**最后更新**:2026-06-15 · 配合 V2 阶段 + `develop` 分支接入准备
