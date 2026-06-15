# Backend Standup Daily

> 角色:后端(2-3 人)
> 写完后 → 通知 PM 汇总 → `pm/standup/summary_YYYYMMDD.md`
> 模板见 `pm/standup/template.md`

---

## W1 · D1 · 2026-06-15(占位)

**Agent**: BE-A (Auth/Users/Materials) / BE-B (中间件/DevOps/Orders)

### ✅ 昨日完成
- (W1 起点)

### 🎯 今日计划
- [ ] BE-A: pyproject.toml 锁定,FastAPI 0.110+ 装好
- [ ] BE-A: app/main.py + app/core/{config,db,security}.py
- [ ] BE-A: SQLAlchemy 2.0 async engine 跑通(连 SQLite 落库)
- [ ] BE-A: alembic init + 4 表 migration 0001_init.py
- [ ] BE-B: .env.example 起好,所有可配项列齐

### 🚧 阻塞
- 无

### 📊 数据
- 项目初始化:0/100%

---

## W1 · D2 · 2026-06-16(占位)

### ✅ 昨日完成
- BE-A: FastAPI 脚手架完成,uvicorn 跑通
- BE-A: alembic upgrade head 成功,4 表落库
- BE-A: JWT + bcrypt 单元测试 PASS

### 🎯 今日计划
- [ ] BE-A: 5 个 auth 端点写完(register/login/sms-login/refresh/send-code)
- [ ] BE-A: Pydantic schema + 错误码(用 V2 §9.3 1xxx-7xxx)
- [ ] BE-B: 限流中间件(60 req/min/IP,慢 API)
- [ ] BE-B: 请求日志中间件(loguru)

### 🚧 阻塞
- 无

### 📊 数据
- API 端点:0/5
- 落库表:4/4

---

## W1 · D3 · 2026-06-17(占位)

### ✅ 昨日完成
- BE-A: 5 个 auth 端点写完,curl 5 个全 200/201
- BE-A: register 流程 register → login → access JWT 跑通
- BE-B: 限流 + 日志中间件接入

### 🎯 今日计划
- [ ] BE-A: pytest tests/test_auth.py 覆盖 5 端点 × happy/error
- [ ] BE-A: 覆盖率 ≥ 80% for app/api/v2/auth/
- [ ] BE-B: docker-compose.yml(后端 + Redis)
- [ ] BE-B: Dockerfile
- [ ] 全员:启动命令 + 端点列表更新到 README

### 🚧 阻塞
- 无

### 📊 数据
- API 端点:5/5
- 覆盖率:待测

---

## W1 · D4 · 2026-06-18(占位)

### ✅ 昨日完成
- BE-A: test_auth.py 全 PASS,覆盖率 82%
- BE-B: docker-compose up 跑通
- BE-A: 把 5 端点的 curl 响应贴到 WORKLOG.md

### 🎯 今日计划
- [ ] BE-A: 配合 FE 端做端到端 demo
- [ ] BE-B: Dockerfile 多阶段构建优化(可选)
- [ ] BE-A: 预留 SMSChannel 抽象 + PaymentAdapter(不接真实)

### 🚧 阻塞
- 无

### 📊 数据
- API 端点:5/5
- 覆盖率:82%

---

## W1 · D5 · 2026-06-19(占位,W1 收口)

### ✅ 昨日完成
- 端到端 demo 跑通
- SMSChannel / PaymentAdapter 抽象接口写好(stub)

### 🎯 今日计划
- [ ] BE-A: W1 末修 bug
- [ ] 全员:WORKLOG.md + WORKLOG.json 收尾

### 🚧 阻塞
- 无

### 📊 数据
- API 端点:5/5
- 覆盖率:82%
- W1 完成度:100%

---

## W2 滚动区域

(每日格式同上,接 W2-D1 2026-06-22)
