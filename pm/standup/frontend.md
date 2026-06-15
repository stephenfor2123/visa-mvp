# Frontend Standup Daily

> 角色:前端(3 人:web/iOS/小程序 + 后台)
> 写完后 → 通知 PM 汇总 → `pm/standup/summary_YYYYMMDD.md`
> 模板见 `pm/standup/template.md`

---

## W1 · D1 · 2026-06-15(占位,W1 启动后填)

**Agent**: FE-A (Web + 后台) / FE-B (iOS) / FE-C (小程序)

### ✅ 昨日完成
- (W1 D1 = 周一 = W1 起点,无昨日)

### 🎯 今日计划
- [ ] FE-A: vite create vue → frontend/web/ 初始化
- [ ] FE-A: vue-router 4 + Pinia 接入
- [ ] FE-B: flutter create --platforms=ios → frontend/ios/(无 android/)
- [ ] FE-B: flutter_localizations + intl 接入
- [ ] FE-C: uni-app x 初始化 → frontend/miniprogram/
- [ ] FE-A: shared/i18n/{zh-CN,en}.json 起 30 key 草案

### 🚧 阻塞
- 无

### 📊 数据
- 项目初始化:0/4 端

---

## W1 · D2 · 2026-06-16(占位)

**Agent**: FE-A / FE-B / FE-C

### ✅ 昨日完成
- FE-A: Vite 项目初始化完成,跑通 npm run dev
- FE-B: Flutter iOS-only 项目初始化,模拟器跑起来
- FE-C: uni-app x 项目初始化

### 🎯 今日计划
- [ ] FE-A: Web 端 i18n 30 key 落地,vue-i18n@9 接入
- [ ] FE-A: 4 端共用 Button/Card/Input 组件
- [ ] FE-B: iOS 端 intl 4 语种 ARB 文件
- [ ] FE-C: 小程序端 P3 登录页静态版

### 🚧 阻塞
- FE-C: uni-app x 在 macOS arm64 上需要 Rosetta,等装

### 📊 数据
- 项目初始化:3/4 端(后台 web 端基于 web 端,顺延到 D3)

---

## W1 · D3 · 2026-06-17(占位)

### ✅ 昨日完成
- FE-A: Web 端 P3 登录页静态版(用 mock 数据)
- FE-B: iOS 端 P3 登录页静态版
- FE-C: 小程序端 P3 登录页静态版
- FE-A: shared/design-tokens.json 锁定

### 🎯 今日计划
- [ ] FE-A: 后台 Web 端初始化(基于 web 脚手架)
- [ ] FE-A: 后台登录页 + Dashboard 占位
- [ ] 全员:登录页接后端 mock(等 B 端 5 端点跑通)

### 🚧 阻塞
- 全员卡 B 端:等 register / login 端点 D2 末出

### 📊 数据
- 登录页静态版:3/4 端完成,后台明天

---

## W1 · D4 · 2026-06-18(占位)

### ✅ 昨日完成
- FE-A: 后台 web 初始化 + 登录页 + Dashboard 占位
- 全员:接通后端 mock 登录(注册→登录→拿 JWT→存 localStorage)
- 截图 4 张:`frontend/{web,ios,miniprogram,admin}/screenshots/login.png`

### 🎯 今日计划
- [ ] 全员:截图 + README
- [ ] FE-A: e2e playwright demo(配合 QA)

### 🚧 阻塞
- 无

### 📊 数据
- 端到端登录:4/4 端(以本地 mock 跑通)

---

## W1 · D5 · 2026-06-19(占位,W1 收口)

### ✅ 昨日完成
- e2e playwright demo 录像成功
- 4 端 README 写好

### 🎯 今日计划
- [ ] 全员:W1 修复 + 收尾
- [ ] FE-A: 把 4 端登录页 4 语种跑一遍(机翻也跑)
- [ ] FE-B: iOS 模拟器最终截图
- [ ] 全员:更新 WORKLOG.md + WORKLOG.json

### 🚧 阻塞
- 无

### 📊 数据
- 4 端登录页可跑:✅ (W1 完成)

---

## W2 滚动区域

(每日格式同上,接 W2-D1 2026-06-22)
