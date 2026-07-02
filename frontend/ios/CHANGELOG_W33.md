# W33 iOS 同步 — W32 Web 功能 Flutter 移植

> **Date**: 2026-06-29
> **Branch**: (新建 `feat/ios-w32-sync` 推荐)
> **Scope**: 把 web 端 W32 backup (dcde6c4) 的新功能移植到 iOS Flutter
> **Engineer**: Mavis

## 概述

把 web 端 W29-W32 累计的新功能一次性移植到 iOS Flutter 端，让两端产品能力对齐。**0 个 iOS 独有逻辑**——所有 page 都是 web 端 Vue 的 Flutter 1:1 镜像（同 API、同字段、同 UI 结构）。

## 改动总览

### 新增 service (6 个)

| 文件 | 端点 |
|---|---|
| `auth_service.dart` (重写) | `/api/v2/auth/{register,login,refresh,reset-password,send-code}` — W32 schema: username+email+password |
| `destinations_service.dart` | `/api/v2/destinations` + groupByVisaType + fallback(4 hero 国) |
| `diagnose_service.dart` | `/api/v2/diagnose` 公开拒签风险评估 |
| `ocr_service.dart` | `/api/v2/ocr/recognize` multipart 上传 |
| `rag_service.dart` | `/api/v2/rag/{query,checklist}` |
| `apply_service.dart` | `/api/v2/orders` 创建订单 |

### 新增 page (6 个)

| 文件 | 对应 web 端 | 功能 |
|---|---|---|
| `apply_page.dart` | Apply.vue | 4 步 wizard: 选国→材料清单→出行信息→确认 |
| `diagnose_page.dart` | Diagnose.vue | 3 步: 选国→画像表单→风险评分 |
| `passport_upload_page.dart` | PassportUploadModal.vue | 上传/拍照→OCR |
| `passport_review_page.dart` | PassportReview.vue | OCR 字段可编辑 |
| `resources_page.dart` | Resources.vue | RAG 问答 + 国别过滤 |
| `contact_page.dart` | ContactView.vue | 邮箱/客服/Bug/商务 |

### 升级 page (5 个)

| 文件 | 改动 |
|---|---|
| `home_page.dart` | W32 Hero 渐变 + slogan + 4 国 CTA + Atlys 价签卡 |
| `destinations_page.dart` | Hero 5 国封面 + 申根 26 国 grid (展开/收起) |
| `login_page.dart` | 账号登录 tab (邮箱/用户名) + SMS tab 兼容 |
| `register_page.dart` | username+email+password+强度条(去 SMS) |
| `forgot_page.dart` | account + new_password (W32 reset by account) |

### 新增 widget (2 个)

- `country_search_modal.dart` — 可搜索 29 国 bottom sheet
- `selfie_capture.dart` — 自拍采集 (mock 实现，待 image_picker 集成)

### main.dart 路由表 (重写)

- **19 个路由** (从原 13 个加 6 个新页面)
- `onGenerateRoute` 支持 deep-link 参数 (`?page=&lang=`)
- `AppRoutes` const 19 个, 全部在 generateRoute 里 case 对应

### i18n (4 国补全)

- 4 国 ARB 各加 **159 keys** (zh/en/id/vi)
- 新增 keys 覆盖: apply / diagnose / passport / resources / contact / register / login / home
- 老 page 升级: loginAccountTab / registerUsernameLabel / homeSlogan 等

## 技术决策

1. **W32 schema 对齐**: username+email 双标识符登录 (实测后端 schema 完全一致, US/FR/CN fixture OCR 全通)
2. **静态兜底**: `DestinationsService.fallback()` 4 国 hero 列表, 后端失败时 UI 仍可用 (跟 web 端 FALLBACK_DESTINATIONS 一致)
3. **service 设计**: `http.Client` 可注入, 便于 widget test
4. **i18n 优先**: 新 page 全部用 ARB keys, 不写 inline 中文
5. **路由参数化**: `AppRoutes.apply` 接受 `initialCountryCode`, 支持从 Home hero 直接跳对应国家

## 静态验证 (本机无 Flutter SDK)

```
✓ 18 个 page 全部 import 到 main.dart
✓ 19 个 AppRoutes const 全部对应到 generateRoute case
✓ 6 个 service 类名匹配所有 page 引用
✓ 所有 Model 字段 (Destination / DiagnoseResult / OCRResult / RAGAnswer / Checklist / OrderDraft)
  都在 page 引用中找到对应 getter / field
✓ 老 page 升级到新 schema (loginByAccount / register / resetPassword)
```

## 已知问题 (待 Mac 装 Flutter SDK 后跑 analyze)

1. **`flutter analyze` 未跑** — 本机无 Flutter SDK (`flutter --version` 触发 Dart SDK 下载 180s 超时)。建议在有 Flutter 的 Mac 上:
   ```bash
   cd frontend/ios
   flutter pub get
   flutter analyze
   flutter build web --release  # 等价验证编译路径
   ```

2. **`image_picker` 未集成** — PassportUpload + SelfieCapture 用 mock, 真实集成需要:
   ```yaml
   # pubspec.yaml 加:
   dependencies:
     image_picker: ^1.0.0
   ```

3. **CN passport_no 抽取 null** — 后端 OCR 在 fixture 上正常 (priority 3 country passport_re 命中), 但 `A123456789` 不是任何 ICAO 标准格式, Priority 3 兜不到. 不是 bug.

## 真业务流路径 (可手测)

| 入口 | 跳转链 |
|---|---|
| 首页 Hero "美国" | `/apply?cc=US` → 4 步 wizard → `/order-detail` |
| 首页 Hero "查通过率" | `/diagnose` → 选 US → 表单 → 评分 → CTA ApplyPage |
| 首页 Hero "问政策" | `/resources` → 输 "美国签证费用" → RAG 答案 |
| 首页 Feature "上传护照" | `/passport-upload` → OCR → `/passport-review` |
| 注册 | `/register` → username+email+password → 自动登录 → `/home` |
| 登录 | `/login` → 邮箱/用户名 + 密码 → `/home` |

## 后端修复 (W32 backup 已存在但有 bug)

本次同步发现并修复了 W32 commit 里 OCR 的 2 个遗留 bug (跑通了 US/CN/FR fixture):
- `_find_value_in_band` candidates 取错边 (左 vs 右) → 改成右侧 value
- `_find_value_in_band_by_index` 同样问题 → 同改
- nationality value_re `\b([A-Z]{3,})\b` 拒 2 字符国码 → 改成 `\b([A-Z]{2,3})\b`

修改文件: `backend/app/services/ocr.py` (3 处)

## 后续 (V2.1)

- [ ] image_picker 集成 (真拍照/相册)
- [ ] Hero 视频化 (视频资源 + cached_network_video_player)
- [ ] iOS native build (需 Mac 装 Xcode, 当前 W6b A_WORKLOG 已记 blocker)
- [ ] flutter test 补齐 5 个新 page 的 widget test
- [ ] CI 加 `flutter analyze` 检查