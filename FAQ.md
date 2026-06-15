# FAQ — 签证助手（Visa Helper）常见问题清单

> 适用对象：开发 / 用户 / 运营三类人群；覆盖 W1–W15 已知问题与最佳实践。
> 最近更新：2026-06-15 · 维护：Coder · 来源：README、API.md、LEGAL_REVIEW_NOTES.md、pm/infra/README.md、CI workflow

---

## 目录

- [Part 1 · 开发 FAQ](#part-1--开发-faq)
  - [1.1 本地启动报错](#11-本地启动报错)
  - [1.2 依赖装不上](#12-依赖装不上)
  - [1.3 测试跑不起来](#13-测试跑不起来)
  - [1.4 CI 失败](#14-ci-失败)
  - [1.5 数据库迁移](#15-数据库迁移)
  - [1.6 依赖冲突 / 版本错乱](#16-依赖冲突--版本错乱)
  - [1.7 前端 Vite / Playwright 常见坑](#17-前端-vite--playwright-常见坑)
- [Part 2 · 用户 FAQ](#part-2--用户-faq)
  - [2.1 怎么注册](#21-怎么注册)
  - [2.2 忘记密码 / 找回密码](#22-忘记密码--找回密码)
  - [2.3 支付失败](#23-支付失败)
  - [2.4 RPA 是什么](#24-rpa-是什么)
  - [2.5 签证状态查询](#25-签证状态查询)
  - [2.6 拒签 / 退款](#26-拒签--退款)
- [Part 3 · 运营 FAQ](#part-3--运营-faq)
  - [3.1 怎么部署](#31-怎么部署)
  - [3.2 数据备份在哪](#32-数据备份在哪)
  - [3.3 监控怎么看](#33-监控怎么看)
  - [3.4 报错去哪看](#34-报错去哪看)
  - [3.5 临时域名 / 联调外网](#35-临时域名--联调外网)
- [附录 A · 错误码速查](#附录-a--错误码速查)

---

## Part 1 · 开发 FAQ

> 主要面向后端 / 前端 / Flutter / 小程序开发同学。所有命令均假设在项目根目录 `签证项目/` 下执行。

### 1.1 本地启动报错

#### Q1.1.1 后端 `uvicorn` 启动报 `ModuleNotFoundError: No module named 'app'`

**原因**：没在 `backend/` 目录里启动 uvicorn，Python 找不到 `app/` 包。

**解决**：

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

或者设 `PYTHONPATH`：

```bash
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8000
```

#### Q1.1.2 前端 `npm run dev` 启动报 `Cannot find module '@shared/...'`

**原因**：`frontend/web/vite.config.js` 里的 alias `@shared` 指向 `frontend/shared/`，第一次 clone 后没装或 alias 配错。

**解决**：

```bash
# 1) 确认 shared 目录存在
ls frontend/shared/i18n/

# 2) alias 在 vite.config.js 已配置，无需手动改：
#    '@shared': path.resolve(__dirname, '../shared')
# 3) 重新装依赖
cd frontend/web && rm -rf node_modules && npm install
```

#### Q1.1.3 前端 dev server 起来但访问页面空白，控制台报 `Failed to fetch /api/v2/...`

**原因**：后端没起 / 端口被占 / `VITE_MOCK` 配置与预期不符。

**解决**：

```bash
# 1) 确认后端健康
curl http://localhost:8000/health
# 期望返回 {"status":"ok","app":"Visa MVP API","version":"0.1.0"}

# 2) 看 vite.config.js 的 proxy 配置
grep -A5 'server:' frontend/web/vite.config.js
# 应有:
#   proxy: { '/api': 'http://127.0.0.1:8000' }

# 3) 想走 Mock 不依赖后端：.env 里设 VITE_MOCK=true
```

#### Q1.1.4 Docker Compose 起服务后 `alembic upgrade head` 失败

**原因**：通常是 `DATABASE_URL` 没传 / Postgres 没起来（CI 才会用到 Postgres，本地 dev 默认 SQLite）。

**解决**：

```bash
# 本地 dev 默认走 SQLite，确认 .env 里：
DATABASE_URL=sqlite+aiosqlite:///./data/visa_mvp.db

# 看容器日志
docker compose logs -f backend

# 重跑迁移
docker compose exec backend alembic upgrade head
```

#### Q1.1.5 Flutter iOS 启动报 `CocoaPods could not find compatible versions for pod ...`

**解决**：

```bash
cd frontend/ios/ios
pod repo update
pod install --repo-update
flutter clean && flutter pub get
```

#### Q1.1.6 微信小程序开发者工具打开 `frontend/miniprogram` 报错「不是小程序项目根目录」

**原因**：`project.config.json` 在 `frontend/miniprogram/`，但打开时选错目录。

**解决**：在微信开发者工具「导入项目」时，**项目目录** 选 `frontend/miniprogram`（不是其上层 `frontend/`）。

---

### 1.2 依赖装不上

#### Q1.2.1 后端 `pip install -r requirements.txt` 报 `paddleocr` 装不上 / 超时

**原因**：PaddleOCR 体积大（~500MB），且依赖特定 Python 版本。`tests/conftest.py` 间接链式触达它时（如 `from app.services.audit import ...`）会卡。

**解决**：

```bash
# 方案 A：用国内镜像
.venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 方案 B：跳过 paddleocr，CI/测试不需要
# 在 requirements.txt 注释 paddleocr 相关行，再装

# 方案 C：单独建一个 .venv-test（不装 paddleocr），跑单元测试
python3 -m venv .venv-test
.venv-test/bin/pip install -r requirements-no-ocr.txt
```

#### Q1.2.2 前端 `npm install` 报 `EACCES` / `permission denied`

**原因**：在 `~/Desktop` 下 clone 触发了 macOS Gatekeeper 或 npm 全局权限问题。

**解决**：

```bash
# 方案 A：用项目本地 node_modules（推荐）
cd frontend/web && rm -rf node_modules && npm install

# 方案 B：清缓存
npm cache clean --force

# 方案 C：不要 sudo！改用 nvm 管理 node
```

#### Q1.2.3 前端装依赖时 `gyp ERR! find Python`

**原因**：`node-sass` / `canvas` / `playwright` 等 native 模块需要 Python。

**解决**：

```bash
# macOS
brew install python@3.11
npm config set python /opt/homebrew/bin/python3.11
rm -rf node_modules && npm install
```

#### Q1.2.4 Flutter `pub get` 卡住 / 报 `GitHub API rate limit`

**解决**：

```bash
# 1) 配镜像（中国大陆）
export PUB_HOSTED_URL=https://pub.flutter-io.cn
export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
flutter pub get

# 2) 或者用国内 fork
git remote set-url origin https://gitee.com/mirrors/flutter.git
```

---

### 1.3 测试跑不起来

#### Q1.3.1 后端 `pytest` 启动后 `50 failed / 2 passed in 0.37s`

**原因**：典型是 `tests/conftest.py` 与 `tests/unit/conftest.py` 的 session-scoped fixture 顺序冲突，或 `_test_env` 触发 `paddleocr` import 链失败。

**解决**：

```bash
# 1) 用 .venv-test（不含 paddleocr）
cd backend
.venv-test/bin/pytest tests/unit/ -v

# 2) 单独跑某个文件（避免 conftest 链式加载）
.venv-test/bin/pytest tests/unit/test_rpa_captcha_solver.py -v
```

> 详细分析见 `~/.mavis/agents/coder/memory/MEMORY.md` 中 "W14-2 verify-only" 条目。

#### Q1.3.2 前端 `npm run test:e2e` 起不来浏览器

**原因**：Playwright 浏览器没装 / 系统缺依赖。

**解决**：

```bash
cd frontend/web
npx playwright install --with-deps chromium
# macOS M 系列如果还是 hang，用 system Chrome:
#   channel:'chrome'  或者 Chrome --headless CLI
```

#### Q1.3.3 前端 E2E 报 `net::ERR_CONNECTION_REFUSED 127.0.0.1:8000`

**原因**：E2E 默认期望后端在 8000 端口运行，没起后端就报这个。

**解决**：

```bash
# 1) 确认后端在跑
curl http://localhost:8000/health

# 2) 或者改成 Mock 模式跑 E2E
VITE_MOCK=true npm run test:e2e
```

#### Q1.3.4 Flutter `flutter test` 报 `Test failed, see ...`

**解决**：

```bash
cd frontend/ios
flutter test --no-pub 2>&1 | tee flutter-test.log
cat flutter-test.log | grep -A3 'Error\|Exception\|Failed'
```

#### Q1.3.5 小程序 `npm run build:weapp:verbose` exit code = 1

**原因**：通常是 `frontend/miniprogram/build_weapp.cjs` 静态校验失败。

**解决**：

```bash
cd frontend/miniprogram
cat build_report.json | jq '.checks[] | select(.status=="FAIL")'
# 按报告里 FAIL 的 check 修，修完再跑
npm run build:weapp:verbose
```

---

### 1.4 CI 失败

#### Q1.4.1 Backend pytest job 在 CI 失败：`alembic upgrade head` 报错

**原因**：CI 用 Postgres（`postgres:16-alpine` service container），但 `alembic.ini` 默认走 sqlite。

**解决**：

```bash
# .github/workflows/ci.yml 已配：
#   sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://visa_test:visa_test@localhost:5432/visa_test|' .env
# 1) 本地复现 CI 环境：
docker run -d --name pg-test -e POSTGRES_USER=visa_test -e POSTGRES_PASSWORD=visa_test -e POSTGRES_DB=visa_test -p 5432:5432 postgres:16-alpine
cd backend
DATABASE_URL=postgresql+asyncpg://visa_test:visa_test@localhost:5432/visa_test alembic upgrade head
```

#### Q1.4.2 Frontend Playwright job 报 `vite build` 超时 / hang

**原因**：macOS M 系列上 vite build 在 Element Plus tree-shake scan 阶段会卡（已知问题）。

**解决**：

```bash
# 1) CI 跑在 ubuntu-latest，本地 Mac 复现不到；直接看 CI artifact
# 2) CI 跑慢可以加：
#      timeout-minutes: 30
#    在 .github/workflows/ci.yml 的 frontend-playwright job
# 3) 本地 build 跳过：
#      node -e "process.exit(0)"  # 只看 ESLint / TS check
```

#### Q1.4.3 Flutter analyze job 失败：`info-level warnings are treated as errors`

**原因**：`--no-fatal-warnings` 配了，但 `--no-fatal-infos` 没配的话，info 会被升级。

**解决**：

```bash
# ci.yml L206 已用：
#   flutter analyze --no-pub --no-fatal-infos --no-fatal-warnings
# 看具体 warning 改：
cd frontend/ios
flutter analyze 2>&1 | head -50
```

#### Q1.4.4 Miniprogram build job：`build_weapp.cjs` exit 1

**原因**：`build_report.json` 里某个 check FAIL。

**解决**：

```bash
# CI artifact 下载 miniprogram-build-report
# 本地复现：
cd frontend/miniprogram
npm run build:weapp:verbose
cat build_report.json | jq '.summary'
```

---

### 1.5 数据库迁移

#### Q1.5.1 改了 SQLAlchemy model 后跑 `alembic upgrade head` 没生效

**解决**：

```bash
cd backend
# 1) 确认 model 真的改了
git diff app/models/

# 2) 自动生成新迁移
.venv/bin/alembic revision --autogenerate -m "describe your change"

# 3) 检查生成的 migration 文件
ls alembic/versions/ | tail -3
# 看最新那个文件内容，确认 upgrade()/downgrade() 正确

# 4) 应用迁移
.venv/bin/alembic upgrade head

# 5) 验证 schema
sqlite3 data/visa_mvp.db ".schema"
```

#### Q1.5.2 多人开发迁移冲突（`Multiple head revisions are present`）

**解决**：

```bash
cd backend
# 1) 看当前 heads
.venv/bin/alembic heads

# 2) 合并
.venv/bin/alembic merge -m "merge heads" <rev1> <rev2>

# 3) 推上去后再 upgrade head
.venv/bin/alembic upgrade head
```

#### Q1.5.3 想重置数据库（开发期）

```bash
cd backend
rm -f data/visa_mvp.db
.venv/bin/alembic upgrade head
# 或者用 create_all 兜底（在 conftest.py 里）
```

#### Q1.5.4 想从 Postgres 切回 SQLite（或反向）

```bash
# 改 .env:
DATABASE_URL=sqlite+aiosqlite:///./data/visa_mvp.db
# 或
DATABASE_URL=postgresql+asyncpg://user:pwd@host:5432/dbname

# 注意：alembic 在 sqlite 和 postgres 之间不通用，
# 如要切，需重新生成 migration 或维护两个版本的 ini。
```

---

### 1.6 依赖冲突 / 版本错乱

#### Q1.6.1 `pip` 装的时候报 `ResolutionImpossible` / 版本冲突

**解决**：

```bash
cd backend
# 1) 看冲突树
.venv/bin/pip install -r requirements.txt --dry-run

# 2) 锁版本。requirements.txt 已锁主版本，但传递依赖可能错：
.venv/bin/pip install pkg==x.y.z

# 3) 重生成 lock（推荐用 pip-tools）
.venv/bin/pip install pip-tools
.venv/bin/pip-compile requirements.in
```

#### Q1.6.2 前端 `npm install` 报 `ERESOLVE unable to resolve dependency tree`

**解决**：

```bash
cd frontend/web
# 1) 用 legacy-peer-deps
npm install --legacy-peer-deps

# 2) 或者用 overrides（在 package.json 里）
#    "overrides": { "vue": "^3.4.0" }

# 3) 清 lock 重装
rm package-lock.json node_modules -rf
npm install
```

#### Q1.6.3 Flutter `version solving failed`

**解决**：

```bash
cd frontend/ios
flutter pub deps -- --json | jq '.packages[] | select(.kind=="transitive")' | head
# 看具体哪个包冲突
# 通常是 pubspec.yaml 里 sdk / flutter 约束太严：
#   environment:
#     sdk: '>=3.4.0 <4.0.0'
```

---

### 1.7 前端 Vite / Playwright 常见坑

#### Q1.7.1 `npm run build` 卡死 / 静默 hang（Mac M 系列）

**原因**：Element Plus tree-shake scan 阶段在 macOS M 系列上有 deadlock。

**解决**：

```bash
# 1) 清 zombie
pkill -f vite

# 2) 跳过 build，用 ESLint + tsc --noEmit 验证
cd frontend/web
npx eslint src --ext .js,.vue
npx vue-tsc --noEmit

# 3) 走 preview HTML + Chrome --headless 截图绕过（参考 memory W14-10/11）
```

#### Q1.7.2 i18n 切换不生效 / 新加 key 没出来

**解决**：

```bash
# 1) 确认 4 语种都加了
grep -n "your_new_key" frontend/shared/i18n/*.json

# 2) 确认前端 import 路径
grep -rn "your_new_key" frontend/web/src/
# 必须从 @shared/i18n 引用，4 端自动同步
```

#### Q1.7.3 Pinia store 状态不持久 / 刷新丢

**解决**：

```bash
# 默认 Pinia 不持久化。要持久化用 pinia-plugin-persistedstate：
cd frontend/web
npm install pinia-plugin-persistedstate
# 在 stores/*.js 里加：
#   persist: true
```

#### Q1.7.4 Playwright 截图找不到元素（`data-testid` 不匹配）

**解决**：

```bash
# 1) 确认页面渲染了对应 testid
grep -rn "data-testid" frontend/web/src/views/

# 2) 用 playwright codegen 现场生成 selector
cd frontend/web
npx playwright codegen http://localhost:5173
```

---

## Part 2 · 用户 FAQ

> 来源：W14 法务 review（`docs/LEGAL_REVIEW_NOTES.md`）+ i18n 文案 + 用户协议条款。
> 这些问题面向 C 端用户，业务文案以最终法务 review 通过版本为准。

### 2.1 怎么注册

#### Q2.1.1 我是第一次用，怎么注册账号？

**步骤**：
1. 打开 Web 端首页 → 点击右上角「注册」
2. 选择国家区号（🇨🇳 +86 / 🇮🇩 +62 / 🇻🇳 +84 / 🇵🇭 +63）
3. 输入手机号 → 点击「发送验证码」
4. 在 60s 倒计时内输入收到的 6 位验证码
5. 设置密码（8–32 位，含字母+数字）
6. 再次输入密码确认
7. 勾选「我已阅读并同意《用户协议》《隐私政策》」
8. 点击「注册」按钮

> **测试期注意**：开发环境 SMS 是 mock 模式，任意 6 位数字都能通过；验证码会直接展示在表单下方（`agreement_required` 行）。

#### Q2.1.2 收不到验证码怎么办？

**可能原因**：
- 手机号格式不对（需带国家区号）
- 同一手机号 1 分钟内请求次数过多（限流：`SMS_RATE_LIMIT` 2010）
- 测试期直接看表单下方 mock 验证码

**解决**：
- 等待 60 秒后重发
- 切换网络或重启手机
- 仍失败请联系客服

#### Q2.1.3 密码有什么要求？

- 长度 8–32 位
- 必须同时包含字母和数字
- 太弱会报 `2004 PASSWORD_TOO_WEAK`

#### Q2.1.4 注册时显示「该手机号已注册」？

**原因**：该号码已注册过（`2003 USER_ALREADY_EXISTS`）。

**解决**：
- 直接登录（走密码登录或短信快捷登录）
- 忘记密码请见 [Q2.2](#22-忘记密码--找回密码)

#### Q2.1.5 注册时勾选协议显示「请先勾选用户协议和隐私政策」？

**原因**：未勾选「我已阅读并同意」复选框。

**解决**：勾上复选框再提交。注意：**默认复选框是未勾选状态**（pre-ticked 在 EU/印尼/越南违法，平台故意默认未勾）。

---

### 2.2 忘记密码 / 找回密码

#### Q2.2.1 忘记密码怎么找回？

> ⚠️ **当前状态（W15）**：密码找回 / 重置端点**尚未上线**（`backend/README.md §9 已知限制` 明列 W2 待做）。

**临时方案**：
- **走「短信快捷登录」**：登录页选「短信登录」标签 → 输入手机号 → 任意 6 位验证码（mock 模式）→ 登录成功
- 进入「个人中心」修改密码（W2 上线后才有此入口）
- **W2 上线后**：登录页会有「忘记密码？」链接，走短信验证码重置流程

#### Q2.2.2 怎么修改密码？

W1 暂未提供独立修改密码端点。W2 计划上线「个人中心 → 修改密码」入口。

#### Q2.2.3 怎么注销账号？

通过隐私政策中提供的客服邮箱申请。处理时限建议 15 个工作日（具体以法务 review 后条款为准，详见 W14-9 法务 review §2.4）。

---

### 2.3 支付失败

#### Q2.3.1 支付时提示「支付失败」怎么办？

**常见原因**（对应后端错误码）：
- **银行卡余额不足**：换卡或充值
- **网络超时**：稍后重试，订单会自动保留 30 分钟
- **风控拦截**（Stripe / 支付宝）：联系发卡行
- **订单已过期**：订单 30 分钟未支付会自动取消（`4002` 报错），需要重新下单

**解决步骤**：
1. 进入「订单详情」→ 点击「重新支付」
2. 更换支付方式（银行卡 / 支付宝 / Stripe）
3. 仍失败请截图保留，联系客服

#### Q2.3.2 支付成功后页面一直显示「待支付」？

**原因**：支付通道回调延迟（通常 5–30 秒内到账）。

**解决**：
- 等待 30 秒后刷新页面
- 或进入「订单详情」→ 点击「刷新状态」
- 系统有 30s 轮询机制（参考 `PaymentResult.vue` 4 states 渲染）

#### Q2.3.3 重复扣款怎么办？

**原因**：银行 / 支付通道可能重复发起了扣款。

**解决**：
- 保留两笔扣款凭证截图
- 联系客服，会在 3–5 个工作日原路退回重复款项
- 走「拒签险条款」或客服申诉均可

#### Q2.3.4 支付完成后多久开发票？

支付完成后可在「订单详情」申请电子发票，1–3 个工作日开具。如需企业发票抬头，请在备注填写完整公司名 + 税号。

---

### 2.4 RPA 是什么

#### Q2.4.1 RPA 是什么意思？

**RPA**（Robotic Process Automation，机器人流程自动化）：平台用软件机器人代替人工，模拟人操作浏览器，自动登录各国签证官网、填写申请表、上传材料、提交申请。

**对你的好处**：
- 24/7 自动提交，不用熬夜等使领馆系统开放
- 提交过程截图存档，可追溯
- 平均节省 2 小时人工填写时间

#### Q2.4.2 RPA 提交需要多久？

预计 **2–5 分钟**。提交过程由 RPA 机器人自动完成，提交成功后你会收到邮件/短信通知。

#### Q2.4.3 RPA 提交失败怎么办？

**自动重试**：系统会在 **30 分钟后自动重试**（参考 `desc_failed` 文案）。

**手动处理**：
- 进入「订单详情」→ 点击「重新提交」
- 或联系客服，提供订单号人工介入

#### Q2.4.4 RPA 提交时我的材料安全吗？

- 所有材料传输使用 **HTTPS / TLS 1.3**
- 加密存储于服务器
- 第三方访问需您明示授权（详见《隐私政策》§3）
- RPA 仅在使领馆官网填写您授权提交的内容，不留存使领馆账号密码

> ⚠️ 跨境数据传输条款以法务 review 后版本为准（W14-9 待复核，详见 `docs/LEGAL_REVIEW_NOTES.md §2.1`）。

---

### 2.5 签证状态查询

#### Q2.5.1 怎么查签证申请进度？

**方法 1 — 在平台查**：
1. 进入「我的订单」
2. 点击对应订单
3. 查看状态卡片（`submitted` / `processing` / `approved` / `rejected` 等）

**方法 2 — RPA 状态查询页面**：
- 进入「RPA 状态查询」页（`status_page_title`）
- 输入订单号或任务 ID
- 实时查询 RPA 提交状态

**状态说明**（来自 i18n 文案）：

| 状态 | 含义 |
|------|------|
| `submitted` | RPA 已将申请提交至签证官网，等待审核开始 |
| `processing` | 使领馆审核中 |
| `approved` | 签证已通过 |
| `rejected` | 拒签，可查看原因 |
| `failed` | RPA 提交失败，30 分钟后自动重试 |
| `abnormal` | 订单状态异常，客服将主动联系您 |

#### Q2.5.2 状态多久更新一次？

- **RPA 提交阶段**：实时更新（每 30s 轮询）
- **使领馆审核**：通常 5–15 个工作日（具体看目的国），状态由使领馆决定

#### Q2.5.3 「订单状态异常」是什么意思？

**含义**：使领馆返回的状态码无法被系统自动归类（可能是网站改版、政策变化、临时维护等）。

**处理**：客服会主动联系你说明情况，请保持手机畅通。

#### Q2.5.4 拒签后能看原因吗？

能。进入「订单详情」→「拒签原因」会展示使领馆返回的官方拒签理由。可据此判断是否申诉或重新申请。

---

### 2.6 拒签 / 退款

#### Q2.6.1 拒签了能退款吗？

**根据《用户协议》§3**：
- **平台原因导致订单失败** → 全额退款
- **用户原因导致拒签** → 按《拒签险条款》处理
- **使领馆政策变化** → 详见 `docs/LEGAL_REVIEW_NOTES.md §2.3`（待法务明确是否构成全额退款条件）

> 拒签险条款的具体生效以法务 review 后版本为准。

#### Q2.6.2 拒签险是什么？

平台提供的增值服务：**若不幸被拒签，平台赔付 100% 服务费**（参考首页特性卡片 `desc` 文案）。

购买入口：创建订单时勾选「拒签险」。

#### Q2.6.3 怎么申诉拒签？

1. 进入「订单详情」→「拒签原因」
2. 确认是否符合申诉条件（材料完整、信息无误）
3. 点击「申诉」→ 提交补充材料
4. 平台 RPA 会重新提交到使领馆

> 具体申诉流程以使领馆要求为准，部分国家不接受申诉。

#### Q2.6.4 退款多久到账？

- 原路退回（银行卡 / 支付宝 / Stripe）
- 通常 3–15 个工作日
- 具体看支付通道处理速度

---

## Part 3 · 运营 FAQ

> 面向运维 / DevOps / 客服 / PM。

### 3.1 怎么部署

#### Q3.1.1 本地 dev 部署（最简单）

```bash
# 后端
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000

# 前端
cd frontend/web
npm install
npm run dev   # http://localhost:5173
```

> B 端 8000 端口 + 前端 vite proxy `/api → 127.0.0.1:8000`，无需 CORS 配置。

#### Q3.1.2 Docker Compose 单机部署

```bash
cd backend
cp .env.example .env  # 改 JWT_SECRET 等
docker compose up --build
# 4 端点就绪在 http://localhost:8000
# Redis 在 localhost:6379
```

容器启动时自动跑 `alembic upgrade head`，数据落 `./.data/visa_mvp.db`，日志在 `./.logs/`。

#### Q3.1.3 多架构镜像构建 + GHCR 推送

```bash
cd backend
./scripts/build-multiarch.sh v0.2.0
# 自动 buildx + push 到 ghcr.io/stephen/visa-api:v0.2.0
```

> 单架构本地用 `docker compose up --build`，多架构发布用独立 buildx 脚本（脚本会忽略 compose.yml 的 build 块）。

#### Q3.1.4 前端生产构建

```bash
cd frontend/web
npm run build       # 输出 dist/
npm run preview     # http://localhost:4173 预览
```

部署到 CDN / Nginx：

```nginx
# /etc/nginx/sites-enabled/visa.conf
server {
    listen 80;
    server_name visa.example.com;
    root /var/www/visa/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

#### Q3.1.5 切换 SMS / Payment 真实通道

W1 都是 Mock。切换真实通道**只改 env，业务代码 0 改动**：

```bash
# .env
SMS_CHANNEL=twilio          # mock → twilio
STRIPE_SECRET_KEY=sk_live_xxx
PAYMENT_ADAPTER=stripe      # mock → stripe
```

新加 `TwilioSMSChannel` / `StripePaymentAdapter` 走工厂方法（详见 `backend/app/services/{sms,payment}/`）。

#### Q3.1.6 CI 自动部署（占位）

W13 已配 `.github/workflows/build.yml` 做多架构镜像构建 + GHCR 推送。**自动部署到生产环境** 待 W16 接入（建议用 ArgoCD / GH Actions self-hosted runner）。

---

### 3.2 数据备份在哪

#### Q3.2.1 SQLite 数据库在哪？怎么备份？

**位置**：
- 本地 dev：`backend/data/visa_mvp.db`
- Docker：`backend/.data/visa_mvp.db`（挂载到容器 `/app/data/visa_mvp.db`）

**备份脚本**：

```bash
#!/bin/bash
# backup_db.sh — 每日凌晨 3 点跑
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/backups/visa-mvp
mkdir -p $BACKUP_DIR
cp /app/data/visa_mvp.db $BACKUP_DIR/visa_mvp_$DATE.db
# 保留 30 天
find $BACKUP_DIR -name "visa_mvp_*.db" -mtime +30 -delete
```

加到 crontab：`0 3 * * * /usr/local/bin/backup_db.sh`

#### Q3.2.2 用户上传的材料文件（护照 / 照片）备份在哪？

W1 没有对象存储，文件存在本地 `backend/uploads/`（如有）。W2 计划迁到 S3 / 阿里云 OSS，备份策略同数据库。

#### Q3.2.3 数据库迁移能回滚吗？

```bash
cd backend
# 回滚到上一个版本
.venv/bin/alembic downgrade -1

# 回滚到 base（清空所有表）
.venv/bin/alembic downgrade base

# 注意：base 会丢所有数据！生产慎用，先备份再回滚
cp data/visa_mvp.db data/visa_mvp.db.bak
.venv/bin/alembic downgrade base
```

#### Q3.2.4 Redis 数据怎么备份？

W2 接 Celery 后才有 Redis 任务。备份方式：

```bash
docker exec visa-mvp-redis redis-cli BGSAVE
# 或
docker exec visa-mvp-redis sh -c 'redis-cli SAVE && cat /data/dump.rdb > /backup/dump_$(date +%Y%m%d).rdb'
```

#### Q3.2.5 多区域灾备（生产）

待 W16 接入：
- 数据库主从 + binlog 同步
- 对象存储跨 region 复制
- Redis Sentinel / Cluster

---

### 3.3 监控怎么看

> W15 已落地「结构化日志」（`outputs/W15-P0-structured-logging`），但**完整 Prometheus + Grafana 监控待 W16 接入**。

#### Q3.3.1 实时日志在哪看？

**后端**（loguru 一行/请求）：

```bash
# 本地
tail -f backend/logs/app.log

# Docker
docker compose logs -f backend
```

**前端**：浏览器 DevTools → Network / Console 面板。

**Nginx**（生产）：

```bash
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

#### Q3.3.2 怎么看 API 错误率？

**方式 1 — 日志 grep**：

```bash
# 最近 1 小时 5xx 数量
grep -c '"status_code": 5' backend/logs/app.log | tail -1

# 按错误码聚合
grep '"code":' backend/logs/app.log | jq -r '.code' | sort | uniq -c | sort -rn
```

**方式 2 — 接入 Prometheus（待 W16）**：

```python
# app/main.py 加 prometheus_fastapi_instrumentator
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
# 暴露 /metrics 给 Prometheus 抓
```

#### Q3.3.3 怎么看限流触发情况？

```bash
# 1009 RATE_LIMIT 出现次数
grep '"code": "1009"' backend/logs/app.log | wc -l

# 按 IP 聚合
grep '"code": "1009"' backend/logs/app.log | jq -r '.client_ip' | sort | uniq -c | sort -rn | head -20
```

限流阈值（`backend/README.md §6`）：
- 全局 100 req/min/IP
- Auth 路由 60 req/min/IP

#### Q3.3.4 怎么看数据库慢查询？

SQLAlchemy `echo=True`（仅 debug 模式）：

```bash
cd backend
ENV=debug .venv/bin/uvicorn app.main:app --reload --port 8000
# 所有 SQL 会打到日志
```

生产推荐接 `sqlalchemy[asyncio]` 的 `engine_connect` 事件 hook + Prometheus histogram。

#### Q3.3.5 怎么看前端性能（Largest Contentful Paint / FCP）？

**本地**：Chrome DevTools → Performance 面板录制。

**生产**：接 Web Vitals SDK（待 W16）：

```js
import { onLCP, onFID, onCLS } from 'web-vitals';
onLCP(console.log);
onFID(console.log);
onCLS(console.log);
```

---

### 3.4 报错去哪看

#### Q3.4.1 后端报错怎么排查？

**步骤**：
1. 看 `backend/logs/app.log`（结构化 JSON，含 rid / 耗时 / 状态码）
2. 找到对应 rid 的请求
3. 看 stack trace

**示例**：

```bash
# 找 5xx 请求
grep '"status_code": 5' backend/logs/app.log | tail -20 | jq .

# 某次请求的完整链路
grep '"rid": "abc123"' backend/logs/app.log | jq .
```

**异常结构**（W15-P0-structured-logging 已统一）：

```json
{
  "ts": "2026-06-14T08:30:00Z",
  "level": "ERROR",
  "rid": "abc123",
  "method": "POST",
  "path": "/api/v2/auth/register",
  "status_code": 500,
  "duration_ms": 234,
  "client_ip": "127.0.0.1",
  "user_agent": "Mozilla/5.0 ...",
  "error": "ModuleNotFoundError: No module named 'foo'",
  "stack": "Traceback (most recent call last): ..."
}
```

#### Q3.4.2 前端报错怎么排查？

**1) 看 console**：
- 浏览器 DevTools → Console
- 看 `console.error` / 未捕获 promise rejection

**2) 看 network**：
- DevTools → Network → 找红色 4xx/5xx 请求
- 点开看 Request / Response / Headers

**3) 接 Sentry（待 W16）**：

```bash
cd frontend/web
npm install @sentry/vue
# main.js 加：
#   import * as Sentry from '@sentry/vue'
#   Sentry.init({ dsn: import.meta.env.VITE_SENTRY_DSN })
```

#### Q3.4.3 CI 报错怎么看？

1. 进入 GitHub Actions → 失败的 workflow run
2. 展开失败的 job → 看 log
3. 关键 artifact（`backend-coverage` / `frontend-playwright-report` / `miniprogram-build-report` / `flutter-analyze-log`）下载到本地分析

#### Q3.4.4 5xx 错误应急响应

```bash
# 1) 看错误码分布
docker compose logs backend --tail=500 | jq -r 'select(.level=="ERROR") | .error_code' | sort | uniq -c | sort -rn

# 2) 1009 / 1010 是限流 / 服务器错误，看触发量是否异常飙升

# 3) 数据库连接错误：检查 DATABASE_URL + Postgres / SQLite 状态
docker compose ps
docker compose logs redis --tail=50

# 4) 重启服务
docker compose restart backend
```

#### Q3.4.5 用户报障收集清单

客服收到用户报障时，请收集以下信息（写入工单系统）：

- [ ] 用户 ID（手机号 / user_id）
- [ ] 订单号（如有）
- [ ] 报错截图
- [ ] 浏览器 / 系统版本
- [ ] 操作步骤（哪一步报错）
- [ ] 报错时间（精确到分钟）
- [ ] 网络环境（WiFi / 4G / VPN）
- [ ] 控制台错误信息（截图）

---

### 3.5 临时域名 / 联调外网

#### Q3.5.1 本地后端怎么暴露到公网给前端 / 真机联调？

用 **ngrok** 或 **cloudflared**：

```bash
# 推荐 ngrok（有 Web UI 调试）
brew install ngrok
ngrok config add-authtoken 2_xxxx
bash pm/infra/start_ngrok.sh
# 输出: https://a1b2c3d4.ngrok-free.app

# 备选 cloudflared（零账号）
brew install cloudflared
bash pm/infra/start_cloudflared.sh
```

> 完整配置见 `pm/infra/README.md`。

#### Q3.5.2 临时域名访问提示「Visit Site」

正常，免费版 ngrok 需要点「Visit Site」按钮；多次访问后会自动通过。

#### Q3.5.3 ngrok quota 用完了

免费版 1GB/月 + 40 req/min。超了换 cloudflared 备选，或买付费（$8/月起）。

#### Q3.5.4 临时域名 CORS 报错

backend/.env 的 `CORS_ORIGINS` 加：

```
CORS_ORIGINS=https://*.ngrok-free.app,https://*.trycloudflare.com
```

重启后端生效。

#### Q3.5.5 想用稳定的域名（团队联调）

- ngrok 付费（$8/月，有固定子域名）
- 或 cloudflared 绑 CF 账号建 named tunnel（免费）

---

## 附录 A · 错误码速查

> 来源：`backend/README.md §3.1` + `frontend/web/README.md` 错误码段。完整定义见 `docs/API.md §5`。

| code | 域 | 含义 | 常见原因 |
|------|----|----|---------|
| `1000` | 通用 | 成功 | — |
| `1001` | 通用 | 参数无效 | 请求体 / query 缺字段或类型错 |
| `1004` | 通用 | 资源不存在 | ID 不对 |
| `1005` | 通用 | 未认证 / Token 过期 | JWT 无效或过期，调 `/auth/refresh` |
| `1006` | 通用 | 无权限 | 角色不足 |
| `1009` | 通用 | 频率限制 | 超过 100 req/min/IP |
| `1010` | 通用 | 服务器错误 | 看后端日志 |
| `2001` | Auth | 账号或密码错误 | 密码错 / 用户不存在 |
| `2002` | Auth | 验证码错误 | SMS_CODE_INVALID |
| `2003` | Auth | 用户已存在 | 该手机号已注册 |
| `2004` | Auth | 密码太弱 | 不符合 8–32 位 + 字母数字 |
| `2005` | Auth | 账号已禁用 | 客服封禁 |
| `2006` | Auth | refresh token 无效 | 过期或被 revoke |
| `2010` | Auth | SMS 限流 | 1 分钟内请求过多 |
| `3001` | User | 用户不存在 | — |
| `4001` | Order | 订单不存在 | — |
| `4002` | Order | 订单不可取消 | 已支付 / 已完成 |
| `4010` | Order | 订单不可编辑 | 状态不允许 |
| `4011` | Order | 提交签名不匹配 | 数据被篡改，重新提交 |
| `7001` | 第三方 | SMS 网关故障 | Twilio 挂了，切回 mock |

---

## 附录 B · 已知问题（Pre-existing）

> 来源：`frontend/web/README.md`「已知问题」段 + W14-9 法律 review + W15 follow-up。

1. **Payment 端点路径不一致**：前端调 `/v2/payment/status/{orderId}`，后端是 `/v2/payment/{order_no}` / `/v2/payment/{order_no}/close`。真后端模式下支付查询/取消/重试会 404。
2. **Admin `/profile` 端点不存在**：前端 `admin.js` 调 `GET /v2/admin/profile`，后端无此端点。建议 login 响应返回 profile。
3. **RPA `/submit` 请求体不匹配**：前端发 `{ order_no }`，后端期望 `{ order_id, country_code, visa_type, passport_data }`。
4. **4 语种协议法务 review 未完成**：W14-9 待复核（deadline 2026-06-25）。launch 前会移除 WARNING banner。
5. **vite build 在 macOS M 系列 hang**：Element Plus tree-shake 死锁。CI 用 ubuntu runner 绕过，本地用 preview HTML + Chrome --headless fallback。
6. **密码找回 / 注销账号 / 修改密码**：W2 上线。
7. **生产环境 SMS / Payment**：W1 是 Mock，W2 切换真实通道。

---

## 附录 C · 维护说明

- **更新频率**：每次 sprint 结束后更新（sprint reviewer 负责）
- **变更流程**：在 `C_WORKLOG.md` 记一行 `FAQ: add Qxxx about yyy`
- **责任分工**：
  - 开发 FAQ → 后端 / 前端 coder
  - 用户 FAQ → 产品 + 客服
  - 运营 FAQ → DevOps + PM
- **法务相关条目**：以 `docs/LEGAL_REVIEW_NOTES.md` 为准；launch 前所有 P0 条目需法务签字

---

**Maintainer**: frontend coder (W15)
**Last updated**: 2026-06-15
**Status**: 初版（W15 deliverable），下个 sprint 根据 launch feedback 迭代