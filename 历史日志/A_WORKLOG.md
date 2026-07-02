# A 前端 (Coder) — 工作日志

> **A 角色**:前端 (Vue3 + Vite + vue-i18n + vue-router + Pinia + Playwright)
> **范围**:`frontend/web/src/` 视图 + 组件
> **不动**:`backend/`、`frontend/web/src/api/`、`frontend/web/src/i18n/` (除 W3 cycle 2 数据契约外)

---

## 时间线

### 2026-06-12 00:32 — W3 cycle 2 OrderNew.vue retrofit

- 把 OrderNew.vue 4 个 native button 改回 AppButton (治本: W2 临时方案 D 改 native 是治标)
- 复用 AppButton.vue W3 新增的 `setOnTrigger` API: 父级 btnRef.value.setOnTrigger(handler) 注入回调
- 模板: `<AppButton ref="XxxBtnRef" ... data-testid="...">label</AppButton>` (移除 @click 直绑)
- script: 4 个 ref + onMounted 注入 4 个 trigger
- npm run build PASS

### 2026-06-12 08:42 — W4 1e50de3b OrderDetail.vue + Materials.vue retrofit

- 复用 W3 治本:OrderDetail.vue 8 个 AppButton 全 ref + setOnTrigger
- Materials.vue 3 个 AppButton 全 ref + setOnTrigger (含 v-if 条件挂载 + watch + nextTick 注入)
- npm run build PASS

### 2026-06-12 09:03 — W4 polish MaterialsValidate.vue retrofit

- 复用 W3 治本:MaterialsValidate.vue 5 个 AppButton 中 3 个主操作 (revalidate/rescanAll/continue) 改 ref + setOnTrigger
- 保留 line 35 (goMaterials 空状态) + line 120 (v-for 内 rescan) @click 直绑:
  - goMaterials 是 v-else-if 一次性,@click OK 且改 ref 收益小
  - v-for 内 rescan 依赖闭包传 r,setOnTrigger 需为每个 item 单独注入,W3 模板未覆盖此场景
- npm run build PASS 8.91s,MaterialsValidate chunk 7.79kB / CSS 5.38kB
- mtime 锁验证:AppButton.vue/OrderNew.vue/OrderDetail.vue/Materials.vue/i18n 全部未动

### 2026-06-12 09:12 — W4 polish-1b plan_6f0c842b verifier-handoff

- plan_6f0c842b 任务目标: MaterialsValidate.vue AppButton 重构 (复用 W3 治本架构, 5-7min)
- 经审计现状已就位 (见 09:03 entry), 本 session 零代码改动
- 验证: `npm run build` PASS 8.79s, 5 个 mtime 锁文件 (AppButton/OrderNew/OrderDetail/Materials/MaterialsValidate) 全部未触碰
- deliverable: `/Users/stephen/.mavis/plans/plan_6f0c842b/outputs/W4-view-MaterialsValidate-only/deliverable.md`

### 2026-06-13 00:16 — W11-1 全 sprint UI polish 收口 (4/4 DoD PASS + 12/12 截图 distinct + cap kill 实战)

- **W10-2 verifier 13 home.* keys 失活修复**: 改 `home.features.{4}` nested dict `{title,desc}` → flat `_title` + `_desc` 双 key (4 locales),加 `home.toast_explore_pending` (4 locales),Home.vue 13 t() keys 4 语种全齐
- **W11-1 全 11 视图 t() 100% 字段覆盖**: 9 views mtime 改 (Home/Login/Register/Materials/MaterialsScan/MaterialsValidate/Destinations/OrderNew/OrderDetail), 2 views 未改 (Profile/NotFound 已合规),共 213 中文行 → 英文/删除,9 个 user-facing 字符串 t() 化 (nationalityOptions 15 国 + mock destinations 9 国 + OrderDetail 9 国 + MaterialsValidate 2 + MaterialsScan 1 + Materials 3 + Login/Register 4 toast/footer/mock-hint)
- **4 语种 i18n 408 leaf keys × 4 locales = 1632 total**, 4 locales mtime 00:12-49/52/56/00 改完 (zh-CN/en/id/vi),新增 28 keys × 4 locales: `country.*` 19 + `home.*` 9 + `common.*` + `materials.*` + `validation.*` + `orders.*` + `login.*`
- **`npm run build` PASS in 13.02s**,dist 重 build (index-BanhgwW3.js 1357.16 kB | gzip: 443.88 kB),mtime 00:15:52
- **真值 grep recipe 0 hit**: `find src/views -name "*.vue" -exec perl -ne 'print "$ARGV:$.:$_" if /[\x{4e00}-\x{9fff}]/' {} \;` = 0 行 (BSD grep 无 -P 替代),配合 11 views 改动 + i18n 补齐
- **12 截图 12/12 file/pixel/size 三层 distinct** (4 lang × 3 page Home/Login/Register),sha256 + 5×1024 字节 sample SHA256 + file size 全部 distinct,反 W6b A-W6-4 教训避免
- **已知 blocker (1/12)**: `Login-vi-VN.png` 4714 字节 (其他 11 张 43-221KB) — vite preview server 5min cache bug,新 build 后 `/login` 路由 SPA 静态资源被 fallback 到 533 字节 index.html。W12+ retry 建议: pkill vite preview + `python3 -m http.server 4174` 重启静态 server
- **cap kill 实战 (15min hit)**: 0-30s 验现状 → 30-700s 改代码/JSON/build/12 截图 (4/4 DoD PASS) → 700-900s 试图修 Login-vi-VN 空白 (cap kill 拦截) → retry 30s 收口: ls 锁定 mtime + 写 deliverable.md + WORKLOG + board + report-back,Login-vi-VN 已知 blocker 显式披露不藏不滚
- 复用模式: L4 i18n full-locale `common.w2_coming_soon: '{feature} W2 接入'` (zh-CN/en/id/vi 4 版) + `country.*` flat key (15 国 + 2 schengen alias) 跨 4 视图复用同一组 keys,避免 4 视图各写一份
