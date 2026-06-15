# AI&RPA Standup Daily (extension)

> 角色:AI&RPA (2 人:OCR/Rules 1 人, RPA/Captcha 1 人)
> 任务规范要求 4 个角色 daily (frontend/backend/qa/pm),这是 bonus 文件,项目管理需要.
> 模板见 `pm/standup/template.md`

---

## W1 · D1 · 2026-06-15(占位)

**Agent**: AI-A (OCR/Rules) / AI-B (RPA/Captcha)

### ✅ 昨日完成
- (W1 起点)

### 🎯 今日计划
- [ ] AI-A: docker/Dockerfile.ocr 起 PaddleOCR + Tesseract 双引擎容器
- [ ] AI-A: 100 张护照样本准备(W3 OCR 准确率测试用)
- [ ] AI-A: 校验规则 15 条 JSON schema 草案
- [ ] AI-B: ddddocr 验证码识别 demo 跑通(任意一张测试图)

### 🚧 阻塞
- 无

### 📊 数据
- OCR 容器:0/100%
- 样本:0/100

---

## W1 · D2 · 2026-06-16(占位)

### ✅ 昨日完成
- AI-A: Dockerfile.ocr 跑通,本地推理一张图 OK
- AI-A: 100 张样本收集 30 张(github + 自己合成)
- AI-A: 校验规则 15 条 JSON 草案 v0.3
- AI-B: ddddocr demo 跑通,准确率 65%(待优化)

### 🎯 今日计划
- [ ] AI-A: 补 100 张样本到 80+
- [ ] AI-A: 校验规则 15 条 JSON v0.5
- [ ] AI-B: 找更复杂验证码样本,测 ddddocr 上限

### 🚧 阻塞
- AI-A: 印尼/越南样本难找,需要请兼职翻译协助

### 📊 数据
- OCR 容器:80%
- 样本:30/100
- ddddocr:65%

---

## W1 · D3 · 2026-06-17(占位)

### ✅ 昨日完成
- AI-A: 样本 80/100
- AI-A: 校验规则 JSON v0.7
- AI-B: ddddocr 仍 65%,准备 CNN 自训

### 🎯 今日计划
- [ ] AI-A: 补样本到 100
- [ ] AI-A: 字段映射 schema 起(护照/身份证/邀请函 3 类)
- [ ] AI-B: CNN 自训 pipeline 雏形(数据集准备)

### 🚧 阻塞
- 无

### 📊 数据
- OCR 容器:90%
- 样本:80/100
- ddddocr:65%

---

## W1 · D4 · 2026-06-18(占位)

### ✅ 昨日完成
- AI-A: 样本 100/100
- AI-A: 字段映射 schema v0.5
- AI-B: CNN 自训 pipeline 雏形

### 🎯 今日计划
- [ ] AI-A: 把校验规则 JSON 给 BE 端做 B4.1 引用
- [ ] AI-B: RPA Playwright 框架骨架(配合 RPA 任务 W2 接入)

### 🚧 阻塞
- 无

### 📊 数据
- OCR 容器:100%
- 样本:100/100
- 校验规则:v0.7

---

## W1 · D5 · 2026-06-19(占位,W1 收口)

### ✅ 昨日完成
- 校验规则 JSON v0.8 给 BE 端
- RPA 框架骨架 v0.5

### 🎯 今日计划
- [ ] W1 末收口
- [ ] WORKLOG.md + WORKLOG.json 收尾
- [ ] W2 准备:OCR 跑通 + RPA demo

### 🚧 阻塞
- 无

### 📊 数据
- W1 准备动作:100% 完成

---

## W2 滚动区域

(每日格式同上,接 W2-D1 2026-06-22)
