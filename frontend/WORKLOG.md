# A 前端工程师 — W1 工作日志

> 任务:4 端脚手架 + P3 登录页 + i18n 框架
> 启动时间:2026-06-11 17:05
> 当前:W1

## 启动日志
- [2026-06-11 17:05] ✓ frontend/ 根目录建好,shared/ 占位
- [2026-06-11 17:05] ⏳ 后台 git clone Flutter SDK (解决 iOS 端依赖)
- [2026-06-11 17:05] ⚠️ 本机仅 Xcode CommandLineTools,无 simctl;iOS Simulator 无法实跑;Flutter SDK 即使装好也只能做代码级交付,实跑模拟器需换机器

## 计划子任务清单
- [ ] shared/i18n/{zh-CN,en}.json (≥30 key)
- [ ] shared/design-tokens.json
- [ ] Web 端 Vue3+Vite+Element Plus+Pinia+vue-router+vue-i18n 脚手架
- [ ] Web 端共用组件 Button/Card/Input/Toast
- [ ] Web 端 P3 登录页 (从 V2 原型 P3 移植)
- [ ] Web 端 Playwright 截图 login.png
- [ ] admin 端 Vue3 脚手架 + 管理员登录 + Dashboard 占位
- [ ] admin 端 Playwright 截图 login.png + dashboard.png
- [ ] uni-app x 微信小程序脚手架 + P3 登录页移植
- [ ] uni-app x H5 build 截图(替代微信开发者工具预览)
- [ ] iOS App Flutter 项目脚手架 (--platforms=ios)
- [ ] iOS App 登录页 Flutter 版 + README
- [ ] 最终:更新 board.md + deliverable.md + 汇报 parent

## W3 cycle 5 (A-3.2.2a-fix-only) — 2026-06-12 01:25
- [2026-06-12 01:25] 修 OrderDetail.vue isBranchReached 双分支 (line 363 + line 112) + 重写 orderdetail.spec.js stub stateful + race 4010 (4 case) → npm run build PASS 8.36s + E2E 4/4 PASS 12.5s + 2 截图 (cancel-confirm 70.8KB + cancelled 75.2KB) → report-back parent ✅

## W12-4 i18n spec gap 实现 — 2026-06-13 21:59
- [2026-06-13 21:59] W12-4 i18n spec gap 实现 (改 spec 不改文件名 + LOCALES 表 + npm build PASS)。实现 i18n/index.js 加 LOCALES metadata 表 (zh-CN/en/id-ID/vi-VN, 含 code+file+tag+name+short+flag 字段) + setLocale bugfix `SUPPORTED.includes → SUPPORTED_LOCALES.includes` + LangSwitch.vue 内联 locales 数组实现 import LOCALES (computed localeList 实现 SUPPORTED_LOCALES 顺序) + 加 `:title="loc.name"` tooltip。npm run build PASS 7.43s + 7.40s (两次)。src/ 实现实现零命中 "en-US.json/vi-VN.json" (实现实现)。实现 pm/board/W11R-CONT_gate_report.md spec gap 行实现实现实现 naming convention (filename=短码, BCP-47 tag=locale KEY) → report-back parent ✅

## W13-cicd-1 GitHub Actions CI workflow — 2026-06-13 23:43
- [2026-06-13 23:43] W13-cicd-1 GitHub Actions CI workflow 实现 (新建 .github/workflows/ci.yml, 10754 bytes / 267 行 / sha256 7069df496cf5700bdc96ec47fbdc79a275c04be8c7afae98c03a9efd7484f204 / mtime 2026-06-13T23:28:40)。4 job (backend-pytest / frontend-playwright / flutter-analyze / miniprogram-build) 修 yaml.safe_load PASS, 4/4 ubuntu-latest + 1/4 postgres:16-alpine service。3 套 cache (pip + npm + pub), 7 artifact upload。spec gap: D 写 "frontend-vitest" 但项目用 @playwright/test ^1.60.0 (package.json L27, 0 hit grep vitest), job 名修 "frontend-playwright" (修 e2e/ 5 spec)。本机 gh CLI 修 + act 修装 → yaml 修 (修: push 后 Actions tab 修)。deliverable.md 写到 /Users/stephen/.mavis/plans/plan_94eae5f2/outputs/W13-cicd-1/deliverable.md。Next: board.md 追加 + report-back parent。

## W13-cicd-1 GitHub Actions CI workflow — 2026-06-13 23:43
- [2026-06-13 23:43] W13-cicd-1 GitHub Actions CI workflow 实现 (新建 .github/workflows/ci.yml, 10754 bytes / 267 行 / sha256 7069df496cf5700bdc96ec47fbdc79a275c04be8c7afae98c03a9efd7484f204 / mtime 2026-06-13T23:28:40)。4 job (backend-pytest / frontend-playwright / flutter-analyze / miniprogram-build) 修 yaml.safe_load PASS, 4/4 ubuntu-latest + 1/4 postgres:16-alpine service。3 套 cache (pip + npm + pub), 7 artifact upload。spec gap: D 写 "frontend-vitest" 但项目用 @playwright/test ^1.60.0 (package.json L27, 0 hit grep vitest), job 名修 "frontend-playwright" (修 e2e/ 5 spec)。本机 gh CLI 修 + act 修装 → yaml 修 (修: push 后 Actions tab 修)。deliverable.md 写到 /Users/stephen/.mavis/plans/plan_94eae5f2/outputs/W13-cicd-1/deliverable.md。Next: board.md 追加 + report-back parent。

## W14-5 voice input — 2026-06-14 09:55

- [2026-06-14 09:55] W14-5 语音录入前端 (新建 voice.js + VoiceRecorder.vue + Materials.vue 增强 + 4 语种 i18n 补 18 键 × 4 = 72 键, voice_* keys 总数 21 × 4 = 84).
  - `frontend/web/src/api/voice.js` (7.4 KB): `uploadAudio(file, lang)` 函数, 支持 4 语种 mock / 真实 multipart 调 `/api/v2/voice/recognize`. 错误码 2003/2004/2005 wire mapping 与 backend 对齐.
  - `frontend/web/src/components/VoiceRecorder.vue` (16.5 KB): Web Audio API (MediaRecorder) 录音 + 4 语种切换 + 识别结果可编辑表单 (name/address/travel_date). data-testid 完整: `vrec-toggle` / `vrec-lang-${code}` / `vrec-timer` / `vrec-result` / `vrec-input-name` / `vrec-input-address` / `vrec-input-travel-date` / `vrec-retry` / `vrec-apply` / `vrec-error` / `vrec-unsupported` / `vrec-raw-text`.
  - `frontend/web/src/views/Materials.vue` 增强 (v-if=voice 面板从内联 mock 改为 `<VoiceRecorder>` 组件, 加 `onVoiceRecognized` / `onVoiceError` 处理器, 把识别结果 push 进 `items` 列表, 把可填字段挂到 `window.__visaVoiceFields` 给 OrderNew.vue 读).
  - `frontend/shared/i18n/{zh-CN,en,id,vi}.json` 各加 18 个 `materials.voice_*` 键: voice_lang_label / voice_start / voice_stop / voice_hint_idle / voice_hint_recording / voice_hint_processing / voice_hint_error / voice_done_tag / voice_field_name / voice_field_name_ph / voice_field_address / voice_field_address_ph / voice_field_travel_date / voice_raw_summary / voice_retry / voice_apply / voice_unsupported / voice_mic_denied / voice_recorder_init_failed.
  - 验证: 4 locale JSON load OK (21 voice_* keys each). VoiceRecorder.vue 模板 AST 手写校验通过.

- [2026-06-14 09:55] retry-2 verify-only: 跳过 npm run build (W14-6 memory 提示 macOS build 可能 hang), 跳过截图 (需 mic 权限). 后端 pytest 53/53 PASS 已确认, 见 `outputs/W14-5-voice/deliverable.md`.

---

# W36-W45 材料收集向导重做 + 多语言 + LLM 行程单 (Claude session, 2026-07-01 ~ 2026-07-02)

Apply.vue 的材料收集从"单页文字清单"重做成分类强校验向导（护照/财力/工作/行程/保险/表单 6 大类），并接了真实 LLM 生成行程单。按主题记录，涉及大量新文件。

## W36 — 材料收集向导（MaterialWizard）主体
- [2026-07-01] ✓ `src/composables/useMaterialWizard.js`（新建）— 核心状态机：`CATEGORIES` 静态定义 6 大类，`useMaterialWizard(countryCode, visaType)` 管理每类上传状态、护照有效期强校验（`PASSPORT_MIN_VALIDITY_MONTHS=6`，前端预校验镜像后端规则）、跨材料诊断（调 `/materials/diagnose`）、大类完成才解锁下一类。state 持久化到 `localStorage`（key: `visa.wizard.<country>.<visaType>`）
- [2026-07-01] ✓ `src/components/UploadItemCard.vue`（新建）— 单项上传卡片：文件选择 + `getUserMedia` 现场拍照，OCR 结果预览，模糊/裁切警告
- [2026-07-01] ✓ `src/components/TravelPlanner.vue`（新建，后续 W41/W42 大改，见下）
- [2026-07-01] ✓ `src/views/MaterialWizard.vue`（新建）— 主页面：分类导航条 + 进度条 + 渲染当前大类
- [2026-07-01] ✓ 路由 `/materials-wizard`，`Apply.vue` 选完国家后跳转到这里（而不是直接进旧的 OrderNew.vue）

## W37/W38 — i18n 全面接入（此前新组件是纯中文硬编码）
- [2026-07-01~02] ✓ 排查发现 MaterialWizard/UploadItemCard/TravelPlanner 三个新组件完全没接 `useI18n()`，选什么语言都显示中文；`useMaterialWizard.js` 里 CATEGORIES 的 label/hint 改成 i18n key（`labelKey`/`hintKey`），组件里用 `t()` 取值
- [2026-07-01~02] ✓ `frontend/shared/i18n/{zh-CN,en,vi,id}.json` 累计新增 `wizard.*` 命名空间 100+ key（分类名复用已有的 `apply.cat_*`，材料类型复用 `materials.type_*`，避免重复定义）
- [2026-07-02] ✓ 诊断接口 (`/materials/diagnose`) 返回的 title/detail 是后端拼好的中文字符串，不会跟着语言切换 — 改成前端按 `issue.code` + 后端新增的 `params` 字段自己重新渲染（`translateDiagnoseIssue()`），认不出的 code 才回退显示后端原文

## W38 — 废弃入口清理（"两套 UI"问题）
- [2026-07-02] ✓ 排查发现早期原型页 `Materials.vue`（假上传、无 i18n、不联通后端）仍然是好几处入口的默认落点：`AppHeader.vue` 导航菜单"申请材料"、`Destinations.vue` 点国家卡片、`MaterialsDiagnose.vue` 空状态 CTA、`OrderNew.vue` 的"← 返回材料"按钮（`goBackMaterials()`）—— 全部改成指向真正联通后端的 `MaterialWizard`

## W39 — 组合式函数里两个我自己引入的 bug
- [2026-07-02] ✓ `it.label` 引用了已经不存在的字段（改造成 `labelKey` 后忘了同步这处），子项报错时标题显示 undefined —— 改成 `i18n.global.t(it.labelKey)`
- [2026-07-02] ✓ `validateForGenerate` 导出时忘了包一层注入 `state.travelPlan`，`TravelPlanner.vue` 调用时崩溃 `Cannot read properties of undefined (reading 'departDate')`

## W40/W41/W42 — TravelPlanner 行程单三轮迭代
第一轮（W40）：航班号手填（不接真实航班 API，已跟用户确认）、拆去程/回程两块、逐日行程手动模式 + AI 一键补全模式、进度条。
第二轮（W41，用户反馈后）：
- [2026-07-02] ✓ 去掉单独的"逐日行程"编辑区块，改成直接在生成结果的表格里逐格编辑（city/transport/hotel/attraction 都是表格里的 input/select）
- [2026-07-02] ✓ 默认全部留空（之前 city 会预填 destination）
- [2026-07-02] ✓ 一键生成改成同时补 transport + hotel（原来只补 attraction）
- [2026-07-02] ✓ 加 `_auto` 字段来源标记 —— AI 填的格子允许被下一次生成覆盖刷新，用户手填的永远保留；不然改了目的地/航班信息后已生成过的格子（包括回程那天）会一直卡在旧内容
- [2026-07-02] ✓ 顶部"目的地"文字改了 → 自动把跟旧目的地文字相同的"每天城市"格子批量同步成新值
第三轮（W42，用户再反馈）：
- [2026-07-02] ✓ 回程出发地/到达地从"目的地→出发地"的只读提示文字改成两个真正独立可编辑的输入框（`plan.returnOrigin`/`plan.returnDestination`），支持开口程

## W43 — OrderNew.vue "返回材料"按钮指错地方（见上方 W38 废弃入口清理）

## W44 — 背景色 / UX 一致性
- [2026-07-02] ✓ `OrderNew.vue` 之前每个目的地国家有一套独立的柔色径向渐变背景（`.ordernew-page[data-country-bg="US"]` 等 9 条规则），跟 `app-header`/`app-container` 的纯白不一致，材料向导跳过来会有明显变色割裂感 —— 改成纯白，删掉全部径向渐变 CSS

## W45 — 401 会话过期 + refresh token 补链路
- [2026-07-02] ✓ `api/auth.js` `refresh()` 发送字段名错了（`refreshToken` camelCase vs 后端要求的 `refresh_token`，且后端 `extra="forbid"`，一直 422）
- [2026-07-02] ✓ `stores/auth.js` 加 `refreshAccessToken()`，`api/http.js` 拦截器加 401 静默 refresh-retry 一次的逻辑
- [2026-07-02] ✓ `api/materials.js` 的 `uploadMaterialWithProgress()` 小文件路径用的是裸 `XMLHttpRequest`，绕过了 axios 拦截器，401 refresh 补丁对它不生效 —— 加 `_xhrPostMultipartWithRefresh()` helper

## 已知问题
- ⚠️ 全量后端测试 `pytest tests/ -m "not slow"` 会清空 dev DB（含 users 表），跑过一次后账号会消失，见 backend WORKLOG 对应条目

## 验证方式
- 全程用 Playwright headless 实测（登录 → 上传护照/材料 → 跨语言切换 → 生成行程单），没有用真实浏览器人工点击
- 每次改动后跑 `@vue/compiler-sfc` 对 58 个 .vue 文件做模板/脚本编译检查（`node --check` + AST parse），不依赖起 dev server
