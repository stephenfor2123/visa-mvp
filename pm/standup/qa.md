# QA Standup Daily

> 角色:测试 + DevOps(本 W1 合并,W2 起拆分)
> 写完后 → 通知 PM 汇总 → `pm/standup/summary_YYYYMMDD.md`
> 模板见 `pm/standup/template.md`

---

## W1 · D1 · 2026-06-15(占位)

**Agent**: QA-A (测试) / Dev (DevOps,暂未到位)

### ✅ 昨日完成
- (W1 起点)

### 🎯 今日计划
- [ ] QA-A: qa/pytest.ini 配置(asyncio mode + 测试路径)
- [ ] QA-A: qa/conftest.py 全局 fixtures (db 重置 / test client / test data)
- [ ] QA-A: requirements-test.txt 锁定 (pytest, pytest-asyncio, pytest-cov, httpx, faker)
- [ ] QA-A: qa/README.md 起好

### 🚧 阻塞
- 无

### 📊 数据
- 测试用例:0

---

## W1 · D2 · 2026-06-16(占位)

### ✅ 昨日完成
- QA-A: pytest 框架就位,`pytest qa/` 可跑(空)
- QA-A: conftest.py 的 db fixture 自动建/清表跑通
- QA-A: 1 个示例测试 `test_register_happy` PASS

### 🎯 今日计划
- [ ] QA-A: 写 register 4 个场景(happy / phone exists / code invalid / password weak)
- [ ] QA-A: 写 login 3 个场景(happy / wrong password / user not exist)
- [ ] QA-A: 写 sms-login 2 个场景(happy / code invalid)
- [ ] QA-A: 等 BE 端 5 端点 D2 末跑通后,补全

### 🚧 阻塞
- 等 BE 5 端点 D2 末(用 mock client 占位测试)

### 📊 数据
- 测试用例:1(占位)

---

## W1 · D3 · 2026-06-17(占位)

### ✅ 昨日完成
- QA-A: register 4 + login 3 + sms-login 2 = 9 个测试
- QA-A: refresh 2 个测试(happy / expired)
- QA-A: send-code 2 个测试(happy / rate limit)

### 🎯 今日计划
- [ ] QA-A: pytest --cov=app/api/v2/auth --cov-report=html
- [ ] QA-A: 覆盖率目标 ≥ 80%
- [ ] QA-A: OpenAPI 3.0 spec 起草(等 BE 完成后用 fastapi 自动生成 + 手动补全)

### 🚧 阻塞
- 无

### 📊 数据
- 测试用例:13
- 覆盖率:待测

---

## W1 · D4 · 2026-06-18(占位)

### ✅ 昨日完成
- QA-A: 覆盖率 82%(目标 80% 达成)
- QA-A: qa/reports/coverage/index.html 生成
- QA-A: 端到端 playwright 框架(配合 FE 跑)

### 🎯 今日计划
- [ ] QA-A: 跑 qa/scripts/run_tests.sh,写 last_run.json
- [ ] QA-A: 覆盖率截图附到 WORKLOG.md
- [ ] QA-A: 配合 FE 跑端到端 demo

### 🚧 阻塞
- 无

### 📊 数据
- 测试用例:13
- 覆盖率:82%

---

## W1 · D5 · 2026-06-19(占位,W1 收口)

### ✅ 昨日完成
- 端到端 e2e 跑通(playwright 录像)
- last_run.json PASS,覆盖率 82%

### 🎯 今日计划
- [ ] QA-A: 修 W1 末 bug
- [ ] QA-A: WORKLOG.md + WORKLOG.json 收尾
- [ ] QA-A: 覆盖率截图保存

### 🚧 阻塞
- 无

### 📊 数据
- 测试用例:13
- 覆盖率:82%
- W1 完成度:100%

---

## W2 滚动区域

(每日格式同上,接 W2-D1 2026-06-22)
