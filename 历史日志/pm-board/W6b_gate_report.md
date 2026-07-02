# W6b Gate Report — 集成测试收口 (iOS build + 小程序 build)

> Sprint: W6b (2026-06-12 续跑)
> Plan: plan_fd293e97 (5 sub-task, max_cycles=4)
> C Verifier 收口时间: 2026-06-12 18:05
> Verifier session: mvs_7e9a02f1aa9d4c158d533fd8dd9d45ad

---

## 1. 5 sub-task 状态汇总

| task | title | producer | 状态 | 备注 |
|---|---|---|---|---|
| B-W6-7 | AppButton 治本闭环 | coder | ✅ DONE | 5 view 覆盖 18/24 → 23/24 (96%), npm run build 8.97s |
| B-W6-8 | OCR 端到端 + 9 国适配 | coder | ✅ DONE | 11/11 pytest PASS, 9 fixture + 装包修复 + ocr.py regex |
| A-W6-4 | iOS App 启动 (Flutter init + i18n + 登录页移植) | coder | ⚠️ **PARTIAL** | 代码在盘 (mtime 17:29-17:45),但 deliverable.md 缺失 / A_WORKLOG 无追加 / 3 截图同 sha / widget_test scaffold 未改 / 未真跑过 flutter build ios |
| A-W6-5 | 微信小程序端启动 | coder | ✅ DONE | 56 源文件 mtime 锁定,5 截图 distinct sha,deliverable 6545 bytes 详尽 |
| **C-W6-6** | **集成测试** | **verifier** | ⚠️ **INCOMPLETE GATE** | 1 failed + 16 passed + 1 xfailed,iOS FAIL 小程序 PASS |

---

## 2. 集成测试 18 case 结果 (C-W6-6)

| # | Test | Subsystem | Result | Notes |
|---|---|---|---|---|
| 1 | test_ios_dir_exists | iOS | ✅ PASS | dir / pubspec / main.dart / Runner.xcodeproj 全在 |
| 2 | test_ios_pubspec_has_required_deps | iOS | ✅ PASS | flutter_localizations/intl/http/shared_preferences/provider 5 dep 全在 |
| 3 | test_ios_l10n_4_arb_present | iOS | ✅ PASS | app_en/zh/id/vi.arb 4 文件 |
| 4 | test_ios_main_dart_uses_4_locales | iOS | ✅ PASS | localizationsDelegates + supportedLocales + runApp 齐 |
| 5 | test_ios_flutter_pub_get | iOS | ✅ PASS | flutter pub get exit 0 |
| 6 | test_ios_flutter_analyze | iOS | ✅ PASS | dart analyze lib/ exit 0 (4 info-level lint 提示,非 error) |
| 7 | **test_ios_widget_test_smoke** | **iOS** | ❌ **FAIL** | **producer bug**: widget_test.dart L16 引用 `MyApp` 但 main.dart 改名 `VisaIosApp`,compile fail |
| 8 | test_ios_flutter_build_ios | iOS | ⏸ XFAIL | env: xcodebuild 不可用 (CommandLineTools,非完整 Xcode). 在有 Xcode 机器上重测 |
| 9 | test_miniprogram_dir_exists | MP | ✅ PASS | app.js/json/wxss/project.config.json/sitemap.json 全在 |
| 10 | test_miniprogram_5_pages_registered | MP | ✅ PASS | 5/5 pages + tabBar 3/3 |
| 11 | test_miniprogram_3_components | MP | ✅ PASS | Button/Input/Card 平铺 12 文件齐 |
| 12 | test_miniprogram_all_json_valid | MP | ✅ PASS | 15 JSON 全合法 |
| 13 | test_miniprogram_all_js_syntax_valid | MP | ✅ PASS | 12 JS 全 `node --check` 过 |
| 14 | test_miniprogram_4_i18n_files | MP | ✅ PASS | zh-CN/en/id/vi 全在 |
| 15 | test_miniprogram_5_pages_4_lang_core_keys | MP | ✅ PASS | 5 页 × 4 语种 × 6 key = 30 断言全过 |
| 16 | test_miniprogram_5_screenshots_present_and_distinct | MP | ✅ PASS | 5 张 sha256 互不相同 (73KB-374KB) |
| 17 | test_miniprogram_6_tabbar_icons | MP | ✅ PASS | tab-{home,dest,me}{,-active}.png 6 张全在 |
| 18 | test_ios_4_arb_key_parity | iOS↔iOS | ✅ PASS | 4 ARB user-facing key set 全等 |

**总计: 16 PASS / 1 FAIL / 1 XFAIL** (3 runs reproducible)

---

## 3. 2 子系统 verdict

### 3.1 iOS Flutter build: **FAIL** (双层失败)
- **代码层 FAIL**: `test/widget_test.dart` 还是 scaffold 默认 `MyApp` 引用
  (producer A-W6-4 没收尾),即使装上 Xcode,`flutter test` 仍 compile fail
- **环境层 XFAIL**: 本机 `xcodebuild` 不可用 (`xcode-select` 指向 CommandLineTools,
  `flutter doctor` 报 "Xcode installation is incomplete")
- **Producer 合规 P0**: deliverable.md 缺失 / A_WORKLOG 无追加 / 3 截图同 sha(造假)
- **业务层 PASS**: source code (main.dart / login_page.dart / 4 ARB / l10n generated)
  静态上完整,4 语种 ARB 翻译实打实,dart analyze 0 error

### 3.2 微信小程序 build: **PASS** (dry-run 静态校验)
- **代码层 PASS**: 56 个源文件 mtime 锁定,15 JSON + 12 JS 全合法
- **结构层 PASS**: 5 页 + 3 组件 + 4 语种 + 6 tabBar + 5 截图 distinct sha
- **i18n 层 PASS**: 5 页面 × 4 语种核心 6 key = 30 断言全过,4 语种 5 页内容都是真翻译
- **环境层 N/A**: 微信原生小程序无 `npm run build:weapp`,真编译需 wechat-devtools-cli
  或 miniprogram-ci (本机无),dry-run 静态校验是合理 fallback

---

## 4. 必修清单 (C 收口前必出)

### A-W6-4 producer (P0)
1. 改 `frontend/ios/test/widget_test.dart` L16: `const MyApp()` → `const VisaIosApp()`
2. 写 `outputs/A-W6-4/deliverable.md` (跟 A-W6-5 一样结构)
3. A_WORKLOG.md 追加 A-W6-4 行
4. 3 张 iOS 截图重做 (真 3 语种页面,不是同 sha 复制;建议装 Xcode 后用 simulator 截,
   或临时用 web/ 端 Login.vue 切 zh/en/id 3 语种截 3 张 design preview)

### D 协调者 (P1)
1. 评估: 集成测试是否在 W6b 当前 cycle 必须 PASS 才能收口?
   - 选项 A: 强制 A-W6-4 修完再收口 (1 cycle 重跑)
   - 选项 B: 接受 A-W6-4 partial 收口,把"修 widget_test + 3 截图"推到 W6b.1
2. 集成测试脚本可作为 V2.1 regression 套件的一部分复用

---

## 5. 已知遗留 (W6b.1 polish)
- iOS `flutter build ios` 需要完整 Xcode (本机 CommandLineTools 不够) — 装 Xcode 后
  `test_ios_flutter_build_ios` 自动从 XFAIL 翻 PASS
- 微信小程序真编译需 wechat-devtools-cli 或 miniprogram-ci (本机无) — 留 V2.1
- iOS `flutter analyze` LSP server crash (analyzer 工具 bug,非代码) — 用 `dart analyze lib/` 绕开
- iOS widget_test.dart scaffold 默认 counter app (`MyApp` + 0/1 counter) — 修后 V2.1 改写
  LoginPage 实际 widget test

---

**W6b 状态: 1/5 producer 必修后即可收口 (C-W6-6 / B-W6-7 / B-W6-8 / A-W6-5 ✅ 4/5 done)**
