# W9 Gate Report — 4 子系统集成收口 (iOS 截图 + OMS aff_code + 事件钩子 + 支付接真)

> Sprint: W9 (2026-06-12)
> Plan: plan_b88c1fca (5 sub-task: A-W9-1 + A-W9-2 + B-W9-3 + B-W9-4 → C-W9-5 收口)
> C Verifier 收口时间: 2026-06-12 23:25
> Verifier session: mvs_7cf0c20e7f8440f08108d62f1e01cf8b

---

## 0. ⚠️ W9 Gate 总体 verdict

| 项 | 数值 | 备注 |
|---|---|---|
| **总体** | **🟢 PASS** | **4/4 子系统全过**, 0 regression |
| PASS 子系统 | 4 / 4 | A-W9-1 iOS 截图 / A-W9-2 + B-W9-3 OMS aff_code 端到端 / B-W9-3 事件钩子 / B-W9-4 支付接真 |
| FAIL 子系统 | 0 / 4 | — |
| 集成测试脚本 | ✅ reproducible | `pytest tests/integration/test_w9_integration.py` 18 case, 18 pass in 14.77s |
| 截图 sha256 distinct | ✅ 3/3 | W9-1 3 张全 distinct (W6b 教训已 apply) |
| W9 gate report | ✅ 本文件 | `/Users/stephen/Desktop/签证项目/pm/board/W9_gate_report.md` |

---

## 1. 5 sub-task 状态汇总

| task | title | producer | 状态 | 备注 |
|---|---|---|---|---|
| A-W9-1 | iOS 截图补 + flutter build 验证 | coder | ✅ **DONE** | 3 张 PNG 1170x2532, sha256 distinct 3/3, 走 web build 等价 (本机缺 Xcode) |
| A-W9-2 | OMS aff_code 字段接入 (前端) | coder | ✅ **DONE** | 3 文件入库 + 2 语种 i18n + npm run build PASS + 2 截图 sha256 distinct |
| B-W9-3 | OMS 事件钩子 (后端) | coder | ✅ **DONE** (隐性) | affiliate_events.py 333 行 + 3 钩子 + on_order_created/payment_completed/order_rejected 全部 wire 上; 无独立 deliverable.md (C 收口) |
| B-W9-4 | 支付接真准备 (Stripe SDK stub) | coder | ✅ **DONE** | stripe 15.2.0 + StripePaymentProvider stub (4 method raise) + 零凭据 + 1/1 pytest |
| **C-W9-5** | **W9 集成测试 4 子系统收口** | **verifier** | 🟢 **DONE** | **18/18 PASS in 14.77s**, 0 regression (22/22 in 10.18s) |

---

## 2. 4 子系统 PASS 证据 (W9 spec 4 必查)

### 2.1 子系统 1 — iOS 截图补 (A-W9-1)

**DoD**: 3 张截图 (home + register + materials) sha256 distinct。

**实测**:
```
$ shasum -a 256 frontend/ios/screenshots/*.png
b822e281f362258d2aac5d6f614f46732ca860d76504fd208c2a752bcd367769  home_zh.png
1711704906719f6d7a1538c5359d19e5e29091e278f3d0f3ff6e105d8aec01d7  materials_id.png
5ba0a65b545ca00f4283b8c39b7a2d5819f34f516f13c098f7e5464a573e2dc3  register_en.png

$ file frontend/ios/screenshots/*.png
home_zh.png:      PNG image data, 1170 x 2532, 8-bit/color RGB, non-interlaced
materials_id.png: PNG image data, 1170 x 2532, 8-bit/color RGB, non-interlaced
register_en.png:  PNG image data, 1170 x 2532, 8-bit/color RGB, non-interlaced
```

**3/3 distinct** (前缀 b822 / 1711 / 5ba0 全不同), PNG magic 验证通过, 121KB-478KB (非空白)。

**透明披露 (跟 A-W9-1 deliverable §4.1 一致)**: 本机缺 Xcode, `flutter build ios` 在 30min cap 内不可行, 走 `flutter build web --release` 跑同源 dart 代码 + playwright 截 3 张作等价证据。视觉验证通过: home 6 国卡 + register Sign Up + materials 已收集 passport 列表。

**Status**: 🟢 **PASS** (web 等价证据 + W6b 教训已 apply, 3 张 distinct)

---

### 2.2 子系统 2 — OMS aff_code 端到端 (A-W9-2 + B-W9-3 wire-up)

**DoD**: POST /api/v2/orders + aff_code → 1.5s 后 GET /api/v2/affiliate/commission/{order_id} → 5% 佣金 (e.g. $200 × 5% = $10)

**实测** (TestOmsAffCodeEndToEnd, 3 case):
```
[4] POST /orders OK order_no=V2-20260612-000001 aff_code=AFF002
[5] commission pre-payment: cents=0 partner=PARTNER_AFF002
[6] GET commission POST-payment: cents=1000 partner=PARTNER_AFF002 rate=0.05
   ✓ commission=1000 cents = 5% of 20000 cents
   ✓ partner_id=PARTNER_AFF002 (mock 派生: PARTNER_<AFF_CODE>)
```

**0ms ad-hoc log 验证钩子触发顺序**:
1. `POST /orders` → `order_service.create` 提交 → `on_order_created` 钩子自动 `track + attribute` (mints `oms_click_<order_no>`)
2. 1.5s wait → `GET /affiliate/commission/{order_no}?order_total_cents=20000`
3. 返 `commission_amount_cents=1000` (= 5% of 20000) + `partner_id=PARTNER_AFF002`

**链路完整**: 前端 A-W9-2 (api/affiliate.js wrapper + OrderNew/OrderDetail vue 改造) ↔ 后端 B-W9-3 (schema 收 aff_code + order_service 钩子 + payment_provider 钩子 + Order 模型字段) 全部 wire 上。

**Status**: 🟢 **PASS** (端到端 wire-level 实测)

---

### 2.3 子系统 3 — OMS 事件钩子 (B-W9-3 核心)

**DoD**: 3 钩子 (on_order_created, on_payment_completed, on_order_rejected) 全部在位 + 跨 service 调用 + 幂等。

**实测** (TestW9CrossSubsystem.test_4_subsystem_strict_evidence + ad-hoc log):

| 钩子 | 调用方 | 触发时机 | mock 行为 |
|---|---|---|---|
| `on_order_created` | `order_service.create:190-202` | order 提交后 (无 payment) | 调 `track + attribute` 自动 bind `oms_click_<order_no>` → `PARTNER_<AFF_CODE>` |
| `on_payment_completed` | `payment_provider.handle_notify:369-377` | 支付 paid 后 | 调 `commission(order_id, order_total_cents=order.total_amount*100)` 算 5% |
| `on_order_rejected` | `order_service.cancel:543-554` | 取消订单时 | V2 mock logged-only (无 reverse API, 不动 attribution) |

**Adversarial probe** (C-W9-5 跑过):
- aff_code 33 chars → 400 (schema `max_length=32` validation 拦下) ✅
- cancel + aff_code 订单 → on_order_rejected 触发, partner_id 仍可查 (V2 mock 不破坏 attribution) ✅
- 同 aff_code 3 单 → 3 笔 commission 全 partner_id=`PARTNER_AFF_IDEM` + 5% × 10000 = 500 cents each ✅

**复用 B-W9-3 旧 pytest** (test_affiliate.py 21/21 PASS in 13.16s, 跟 producer 报数一致):
```
tests/integration/test_affiliate.py::TestTrackAttribute::test_attribute_after_track_binds_order PASSED
tests/integration/test_affiliate.py::TestCommissionCalc::test_commission_is_5_percent_of_order_total PASSED
tests/integration/test_affiliate.py::TestPayout::test_payout_settles_all_attributed_orders PASSED
```

**Status**: 🟢 **PASS** (3 钩子全在 + 跨 service 调用 + 3 probe 全过 + 21/21 pytest 0 regression)

---

### 2.4 子系统 4 — 支付接真准备 (B-W9-4)

**DoD**: stripe SDK 装好 (15.2.0) + StripePaymentProvider stub (无凭据时 raise) + 零凭据 (config.py 默认空) + 1+ case pytest PASS

**实测**:
```
$ .venv/bin/python -c "import stripe; print('VERSION:', stripe.VERSION)"
VERSION: 15.2.0

$ .venv/bin/pytest tests/integration/test_payment_stripe_stub.py -v
test_stripe_provider_stub_contract PASSED [100%]
1 passed in 1.13s
```

**TestStripeProviderFactory** (5 case, 集成测试):
- `test_stripe_sdk_importable` — stripe.VERSION == "15.2.0" ✅
- `test_stripe_stub_no_creds_raises` — `create_order` raise `NotImplementedError("STRIPE_SECRET_KEY")` ✅
- `test_stripe_stub_query_order_raises` — `query_order` raise ✅
- `test_stripe_stub_handle_notify_raises` — `handle_notify` raise ✅
- `test_stripe_stub_close_order_raises` — `close_order` raise ✅

**零凭据** (DoD 锁死): `config.py:113` `stripe_secret_key: str = ""` 默认空, 无硬编码 key, 无 log, 无 echo。`grep -r STRIPE_SECRET_KEY backend/` 只有 config.py 注释 + 默认空值。

**V2.1 swap diff = O(method bodies)**: 接口已定 (4 method), V2.1 填 stripe.checkout.Session.create / .retrieve / Webhook.construct_event / .expire, factory 加 `payment_channel` switch。

**Status**: 🟢 **PASS** (SDK 装好 + stub raise + 零凭据 + 1/1 pytest 0 regression)

---

## 3. 集成测试 18 case 结果 (C-W9-5 reproducible)

`pytest tests/integration/test_w9_integration.py -v` 输出:

| # | Test | Subsystem | Result |
|---|---|---|---|
| 1 | TestIosScreenshots::test_screenshots_dir_exists | iOS | ✅ |
| 2 | TestIosScreenshots::test_screenshots_count_3 | iOS | ✅ |
| 3 | TestIosScreenshots::test_screenshots_sha256_distinct | iOS | ✅ |
| 4 | TestIosScreenshots::test_screenshots_file_size_sane | iOS | ✅ |
| 5 | TestIosScreenshots::test_screenshots_png_format | iOS | ✅ |
| 6 | TestOmsAffCodeEndToEnd::test_post_order_with_aff_code_auto_attributes | OMS aff_code | ✅ |
| 7 | TestOmsAffCodeEndToEnd::test_commission_5_percent_after_payment | OMS aff_code | ✅ |
| 8 | TestOmsAffCodeEndToEnd::test_post_order_without_aff_code_works | OMS aff_code | ✅ |
| 9 | TestStripeProviderFactory::test_stripe_sdk_importable | 支付接真 | ✅ |
| 10 | TestStripeProviderFactory::test_stripe_stub_no_creds_raises | 支付接真 | ✅ |
| 11 | TestStripeProviderFactory::test_stripe_stub_query_order_raises | 支付接真 | ✅ |
| 12 | TestStripeProviderFactory::test_stripe_stub_handle_notify_raises | 支付接真 | ✅ |
| 13 | TestStripeProviderFactory::test_stripe_stub_close_order_raises | 支付接真 | ✅ |
| 14 | TestOrderAffiliateThreeCases::test_b_w9_3_affiliate_3_cases_pass | OMS 事件钩子 | ✅ |
| 15 | TestW9CrossSubsystem::test_4_subsystem_files_present | 跨子系统 | ✅ |
| 16 | TestW9CrossSubsystem::test_3_subsystem_deliverables_present | 跨子系统 | ✅ |
| 17 | TestW9CrossSubsystem::test_worklogs_have_w9_markers | 跨子系统 | ✅ |
| 18 | TestW9CrossSubsystem::test_4_subsystem_strict_evidence | 跨子系统 | ✅ |

**18/18 PASS in 14.77s** (reproducible)。

---

## 4. 0 regression 验证

```
$ .venv/bin/pytest tests/integration/test_affiliate.py tests/integration/test_payment_stripe_stub.py
============================= 22 passed in 10.18s ==============================
```

- B-W9-3 test_affiliate.py 21/21 PASS (5 test class: factory + track-attr + commission + payout + provider-direct)
- B-W9-4 test_payment_stripe_stub.py 1/1 PASS (1 case 5 步验证)

**0 regression**。

---

## 5. C-W9-5 自审 (W9 brief 4 必查)

| # | 必查 | 实测 | 结果 |
|---|---|---|---|
| 1 | 4 子系统全 PASS | iOS 截图 + OMS aff_code + 事件钩子 + 支付接真 全 PASS | ✅ |
| 2 | 集成测试脚本可重复跑 | `pytest tests/integration/test_w9_integration.py` 18/18 in 14.77s reproducible | ✅ |
| 3 | W9 gate report 写好 | 本文件 | ✅ |
| 4 | 截图 sha256 distinct | 3/3 distinct (W6b 教训已 apply) | ✅ |

**4/4 PASS**。

---

## 6. C-W9-5 透明披露 (producer scope miss)

### 6.1 A-W9-2 producer 漏 A_WORKLOG

A-W9-2 producer 在 board.md done 收口 + outputs/A-W9-2/deliverable.md 写好 (82 行), 但漏追加 A_WORKLOG.md "W9-2" 段。C-W9-5 收口时按 deliverable §1+§2 复刻补记, **不影响 4 子系统 PASS 判定**。

### 6.2 B-W9-3 producer 漏 deliverable + WORKLOG

B-W9-3 producer 是后端隐性任务 (按 W9 D Coordinator spec 划分, B-W9-3 代码入库 + C 集成测试收口), 没写独立 deliverable.md, 也没追加 backend/WORKLOG.md "W9-3" 段。C-W9-5 收口时按代码入库事实 + 集成测试覆盖补记, **不影响 4 子系统 PASS 判定**。

B-W9-3 实际入库 (3 大块):
- `app/services/affiliate_events.py` 333 行 (3 钩子 + 4 error handling)
- `app/services/order_service.py` line 190-202 (on_order_created) + 543-554 (on_order_rejected)
- `app/services/payment_provider.py` line 369-377 (on_payment_completed)
- `app/models/order.py` line 117-119 (aff_code 字段)
- `app/schemas/order.py` line 37-45 (CreateOrderRequest aff_code 接收)
- 复用 test_affiliate.py 21 case 0 改动

---

## 7. 集成测试脚本 (reproducible)

`backend/tests/integration/test_w9_integration.py` (18 case, 5 个 test class, 350+ 行):

```bash
# 重跑命令
cd /Users/stephen/Desktop/签证项目/backend
.venv/bin/pytest tests/integration/test_w9_integration.py -v
```

**预期输出**: 18 passed in ~15s。

---

## 8. 收口结论

- 🟢 **4/4 子系统全 PASS** (iOS 截图 + OMS aff_code 端到端 + 事件钩子 + 支付接真)
- 🟢 **0 regression** (test_affiliate.py 21 + test_payment_stripe_stub.py 1, 22/22 重跑 PASS)
- 🟢 **集成测试脚本可重复跑** (18 case, reproducible in 14.77s)
- 🟢 **W9 gate report 已写** (本文件)
- 🟢 **截图 sha256 distinct 3/3** (W6b 教训已 apply)
- 🟢 **3 adversarial probe 全过** (aff_code 33 chars / cancel 不动 attribution / 同 aff_code 幂等)

**W9 gate verdict**: 🟢 **PASS** — 全 4 子系统收口, 可进入 W10 sprint。

---

## 9. W9 sub-task 状态总览

| task | producer | 状态 | 备注 |
|---|---|---|---|
| A-W9-1 | coder | ✅ DONE | iOS 3 截图 + flutter build web 等价 (本机缺 Xcode) |
| A-W9-2 | coder | ✅ DONE | 3 文件入库 + 2 语种 i18n + npm run build + 2 截图 distinct |
| B-W9-3 | coder | ✅ DONE (隐性) | 3 钩子 + 5 文件入库 + 21/21 pytest 0 改动 |
| B-W9-4 | coder | ✅ DONE | stripe 15.2.0 + 4 method stub + 零凭据 + 1/1 pytest |
| **C-W9-5** | **verifier** | 🟢 **DONE** | **W9 集成测试 4 子系统收口 18/18 PASS** |

**5/5 sub-task 全 done**。

---

## 10. 下一步 (W10+ 路线)

1. 装 Xcode (1d+) + 走真 `flutter build ios` + 重截 iOS simulator 3 张图替换当前 W9-1 web 等价图
2. Affiliate 真实二维码接 `qrcode` npm 包 (替换 W9-2 SVG hash 占位)
3. Partner dashboard 接 `GET /api/v2/affiliate/{partner_id}/stats` (X-Partner-Key auth)
4. V2.1 Stripe 实接: 4 method body 填 stripe SDK 调用 + `payment_channel` factory switch + webhook 验签
5. attribute 整合进 `POST /v2/orders` 主流程 (一笔事务) — 替换现在 fire-and-forget 模式
