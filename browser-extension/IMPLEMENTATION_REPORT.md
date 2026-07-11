# Htex DS-160 插件 v0.2 · 实施报告

> 日期: 2026-07-09 · 状态:**✅ 实施完成, 全量测试通过, 待真表核对**
> 设计稿: [DESIGN-v0.2.md](./DESIGN-v0.2.md) · [backend-ds160-code-api.md](./backend-ds160-code-api.md)
> 真表核对: [DS160_VERIFICATION_CHECKLIST.md](./DS160_VERIFICATION_CHECKLIST.md)

---

## 📦 交付物总览

| 类别 | 文件 | 状态 |
|---|---|---|
| **设计文档** | DESIGN-v0.2.md (574 行) | ✅ 完成 |
| **API 设计** | backend-ds160-code-api.md (590 行) | ✅ 完成 |
| **时序图** | e2e-flow.mmd (85 个事件) | ✅ 完成 |
| **实施总结** | deliverable.md (159 行) | ✅ 完成 |
| **核对清单** | DS160_VERIFICATION_CHECKLIST.md | ✅ 完成 |
| **后端代码** | 4 个新文件 + 3 个改动 | ✅ 完成 |
| **后端测试** | 46 单测 + 13 集成 | ✅ 59/59 通过 |
| **插件代码** | popup + background 重写 + manifest 更新 + content-ds160 小改 | ✅ 完成 |
| **插件测试** | 25/25 jsdom 测试 | ✅ 通过 |
| **零回归** | 旧 22 orders + 7 my_applicants 测试 | ✅ 全过 |
| **总测试数** | — | **88/88 ✅** |

---

## 🔧 实施改动总览

### 后端 (新增 / 修改)

| 文件 | 改动 | 行数 |
|---|---|---|
| `backend/app/models/order.py` | +7 列 (ds160_code / ds160_fingerprint / ds160_code_issued_at / ds160_code_consumed_count / ds160_last_redeemed_at / ds160_code_revoked / ds160_revoked_codes) | +20 |
| `backend/app/core/ds160.py` | **新文件** — fingerprint + code 生成 + profile 加载 + rate limiter | 290 |
| `backend/app/core/errors.py` | +6 个 DS-160 错误码 (11001-11006) | +10 |
| `backend/app/api/v2/ds160.py` | **新文件** — /code + /redeem 端点 | 350 |
| `backend/app/api/v2/__init__.py` | 注册 ds160 router | +3 |
| `backend/scripts/migrate_ds160_code_fields.py` | **新文件** — 幂等迁移脚本 (SQLite + Postgres) | 95 |
| `backend/tests/conftest.py` | +1 行 (ds160 router get_db patch) + ds160 limiter reset | +8 |
| `backend/tests/unit/test_ds160.py` | **新文件** — 46 个单测 | 410 |
| `backend/tests/api/test_ds160_api.py` | **新文件** — 13 个集成用例 | 410 |

### 浏览器插件 (新增 / 修改 / 删除)

| 文件 | 改动 |
|---|---|
| `browser-extension/popup.html` | **重写** — 12 位 code 输入 + IDLE/READY 双视图 |
| `browser-extension/popup.js` | **重写** — 输入校验 + redeem 调用 + 错误码 → 文案映射 |
| `browser-extension/src/background.js` | **重写** — POST /redeem + storage.session 中转 + meta 缓存 |
| `browser-extension/manifest.json` | **更新** — 移除 htexvisa.com 注入, 加 api.htexvisa.com host |
| `browser-extension/src/content-ds160.js` | **小改** — 读 HTEX_GET_META + 顶部 order_id/fingerprint + login hint |
| `browser-extension/test/mock-ds160.html` | **小改** — 加 mock redeem 按钮 |
| `browser-extension/src/content-app.js` | **删除** — v0.1 同机 postMessage 路径不再用 |
| `browser-extension/test/integration/run-fill-integration.mjs` | **删除** — v0.1 测试覆盖的路径已废弃 |
| `browser-extension/package.json` | 更新 test script |

### 设计 / 文档

| 文件 | 行数 |
|---|---|
| `DESIGN-v0.2.md` | 574 |
| `backend-ds160-code-api.md` | 590 |
| `e2e-flow.mmd` | 116 |
| `deliverable.md` | 159 |
| `DS160_VERIFICATION_CHECKLIST.md` | 246 |
| `IMPLEMENTATION_REPORT.md` | (本文) |

---

## 🎯 5 条决策 · 全部锁定

| 决定 | 你的选择 | 实现位置 |
|---|---|---|
| 登录 DS-160 | 插件只提示，用户自己登 | `content-ds160.js` 加 `maybeShowLoginHint()` 黄色提示；popup 不提供密码输入；后端 `/redeem` 不要求 password |
| Code 语义 | 档案指纹 | `core/ds160.py:compute_fingerprint()` SHA-256 32 hex |
| Code 有效期 | 长期 | `Order.ds160_code` 一直保留；只在 `ds160_code_revoked` 或 `ds160_revoked_codes` 时失效 |
| Code 绑定 | 绑订单 | Order 模型按现有 user_id+order_id 锁；`api/v2/ds160.py:issue_ds160_code` 校验 `order.user_id == current_user.id` |
| Code 校验 | 插件要校验老 code | 后端 redeem 时重算 fingerprint + 比对，**不匹配 → 409 ARCHIVE_CHANGED** |

---

## 🔐 安全模型 · 4 道防线

```
1. Code 随机性 ──── 12 位 base30, ~60 bits 熵 (secrets.choice)
2. Rate limit  ──── 60s / 5 次 / order + 60s / 10 次 / IP (in-memory, P1 Redis)
3. Fingerprint ──── SHA-256(规范化档案快照), 改任一字段 → 老 code 自动失效
4. Revoked list ── force_rotate 把老 code push 到 ds160_revoked_codes JSON,
                    /redeem 先检查再比对 fingerprint, 命中 → 409 CODE_REVOKED
```

**后端零 PII 存储**: `ds160_fingerprint` 不可逆；`ds160_code` 是 random index；真档案在既有 `Order.applicant_data`。

**HTTPS-only**: manifest host_permissions 限定 `https://api.htexvisa.com/*`，本地 dev 用 `localhost:8000`。

**Audit log**: 每次 `/redeem` 调用都写一行 `audit_log`（成功 + 失败 + 失败原因），admin `/logs` 端点能查到。

---

## 🧪 测试矩阵 · 88/88 全过

### 后端单测 (46)

| 类别 | 用例 | 关键守卫 |
|---|---|---|
| generate_code | 4 | 格式 / 字符集 / 1000 次无碰撞 |
| normalize_code_input | 3 | 大小写 / 标点 / 空值 |
| is_valid_code_format | 4 | 合法 + 过短 + 过长 + 混淆字符 |
| load_applicant_profile | 5 | 空 / 坏 JSON / 别名优先级 / to_dict |
| normalize_date | 13 | ISO/DDMMYYYY/MRZ + unparseable → empty |
| compute_fingerprint | 9 | **改任一字段 → 雪崩** / 大小写 / 日期归一 / avalanche 强度 / 缺 section |
| has_minimum_fields | 4 | 5 个必填字段校验 |
| InMemoryRateLimiter | 5 | 阈值 / 独立 key / 窗口重置 / reset |

### 后端集成 (13)

| 端点 | 用例 | 关键守卫 |
|---|---|---|
| /code | 6 | 幂等 / 改档案重生 / 非 owner 403 / 字段缺失 422 / 终态 409 / force_rotate 黑名单 |
| /redeem | 7 | happy path / 格式 400 / 未知 code 404 / **ARCHIVE_CHANGED 409** / **限频 429** / 无 session 也能调 / audit 落库 |

### 既有测试 (29, 零回归)

- `tests/integration/test_orders.py` — 22 通过
- `tests/integration/test_my_applicants.py` — 7 通过

### 插件 jsdom (25)

- `test:fill-engine` — 12 通过 (text/select/date-split/autoFill/not_found/manual)
- `test:mapping` — 13 通过 (字段映射 + valueMap + when 条件)

---

## 📊 跑一遍的实际命令 + 输出

### 单测

```
$ PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_ds160.py -v
============================== 46 passed in 0.24s ==============================
```

### 集成

```
$ PYTHONPATH=. .venv/bin/python -m pytest tests/api/test_ds160_api.py -v
======================== 13 passed in 1 warning in 9.70s ========================
```

### 全量

```
$ PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_ds160.py tests/api/test_ds160_api.py tests/integration/test_orders.py tests/integration/test_my_applicants.py
======================== 88 passed, 1 warning in 27.35s ========================
```

### 迁移脚本 (幂等)

```
$ PYTHONPATH=. .venv/bin/python scripts/migrate_ds160_code_fields.py
INFO  skip ds160_code (already exists)
INFO  skip ds160_fingerprint (already exists)
...
INFO  ensure index: CREATE INDEX IF NOT EXISTS ix_orders_ds160_code ON orders (ds160_code)
INFO  migration complete
```

### 插件 jsdom

```
$ cd browser-extension && npm test
✓ Sex = FEMALE
✓ NationalId DoesNotApply 勾
...
25/25 通过
```

---

## 🐛 实施过程中踩的 5 个坑（顺便记一下）

1. **router prefix 漏写** — `APIRouter()` 必须加 `prefix="/ds160"`，否则端点暴露在 `/code` 而不是 `/ds160/code` → 全部 404
2. **错误响应格式猜错** — BizException handler 返回的是 `{code, message, data}` 平铺，**不是** `{detail: {code}}` 嵌套，跟 FastAPI 默认不一样
3. **Pydantic 校验先于业务** — `min_length=12` 在 path 阶段就拦了"too-short"，业务层的 `11004 INVALID_FORMAT` 没机会触发
4. **撤销设计死结** — `Order.ds160_code` 单列没法存老 code 黑名单，最终加了 `ds160_revoked_codes` JSON 列 + redeem 端 LIKE 模糊匹配 (带引号边界防误中)
5. **测试 bug 当算法 bug** — `test_changing_any_field_changes_fingerprint` 用 `"NEW"` 当 dob 值，被 normalize_date 变成空字符串所以指纹不变 —— 测试本身错了，算法正确

---

## ⚠️ 已知限制与待办

### P0（上线前必须）

- [ ] **L1 真表核对** — 运营/产品拿 [DS160_VERIFICATION_CHECKLIST.md](./DS160_VERIFICATION_CHECKLIST.md) 在真 Chrome 里逐条核；完成后改 `DS160_VERIFIED_DATE = 'YYYY-MM-DD'`
- [ ] **L6 CI check build-extension-mapping** — 防 web 端改 mapping 后插件没同步

### P1（短期优化）

- [ ] Redis 化 rate limiter（现在 in-memory，多 worker 不共享）
- [ ] 跨页累计进度 (`chrome.storage.session.htex_ds160_progress` 后端已经能用，前端面板还没接进度徽标）
- [ ] iframe 注入支持（DS-160 部分页用 frame）
- [ ] revoked_codes 改独立表（JSON LIKE 模糊匹配不能 scale）
- [ ] Htex Web 订单详情页加 "去 DS-160 填表" 按钮 + code 展示（**当前后端 API 已经支持，前端没接**——你看哪个 .vue 我去加）

### P2（远期）

- [ ] 多申请人选择器（当前填 `applicants[0]`）
- [ ] DS-160 会话超时 20 分钟自动续填
- [ ] 跨设备扫码 E2E（**优先级降低** —— 现在已经默认跨设备，PC 装插件即可）

---

## 🚀 上线步骤

1. **代码 review** — 你或同事 review 这一波改动
2. **跑迁移** — `cd backend && PYTHONPATH=. .venv/bin/python scripts/migrate_ds160_code_fields.py`
3. **重启后端** — 新 router 生效
4. **前端订单详情页加按钮** — 告诉我哪个 .vue 我去加
5. **真表核对** — 按 CHECKLIST 走一遍
6. **真机端到端** — 装插件 + 完整跑一次
7. **merge + 部署**

---

## 💡 设计亮点回顾

> Code = 档案指纹, 不是鉴权令牌

```python
# 用户改了任一字段 → fingerprint 雪崩 → 老 code 在插件 redeem 时被后端 409 拒掉
fp = hashlib.sha256(json.dumps(flat_normalized)).hexdigest()[:32]
```

- 比短码一次性高级：老数据不会填到新表单
- 比 session token 简单：用户改档案自动换 code，不用主动失效
- 后端零 PII：fingerprint 不可逆，code 跟档案没关系

---

## 🎁 顺手挖出来的 3 个隐藏改进

1. **审计通道免费** — 项目已有的 `audit_log` 表（43 行），直接复用 `actor_type='system'` + `action='ds160.code.redeem'`，admin `/logs` 自动能查到所有 redeem 尝试
2. **迁移脚本跨方言** — `PRAGMA table_info` (SQLite) + `information_schema.columns` (Postgres) 双分支，幂等跑就行
3. **Pydantic 校验作为第一道防线** — `min_length=12` 早早拦住格式错误的 code，业务层 `INVALID_FORMAT` 只处理"12 字符但含混淆字符"的边缘情况，分层清晰