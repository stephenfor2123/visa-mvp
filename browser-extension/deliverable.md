# Htex DS-160 浏览器插件 v0.2 · 设计交付包

> 日期: 2026-07-09 · 状态:**设计稿完成, 待实现**
> 配套源码: `browser-extension/` (v0.1 实现, 需按本设计升级)
> 决策来源: 与产品方 4 轮 ask_user 对齐 (登录方式 / code 语义 / 绑定粒度 / 交付形式)

---

## 📦 三个交付物

| 文件 | 行数 | 内容 |
|---|---|---|
| **`DESIGN-v0.2.md`** | ~470 行 | 主设计文档: 架构 / 数据流 / 组件清单 / 安全 / 路线图 |
| **`backend-ds160-code-api.md`** | ~430 行 | 后端 API: 2 端点 + DB schema + fingerprint 算法 + 测试矩阵 |
| **`e2e-flow.mmd`** | ~85 个事件 | 端到端时序图: 4 阶段 + 错误路径 + 安全事件 |

合计 ~1000 行设计, **0 行新代码**(代码全在 v0.1 已有, 等你拍板后我再写实现)。

---

## 🎯 你定的 5 条关键决定(锁死, 别忘)

| # | 决定 | 一句话 |
|---|---|---|
| 1 | 登录 DS-160 | **插件只提示, 用户自己登** (我们只干填表) |
| 2 | 12 位 code 语义 | **档案指纹** (code 跟着档案内容走, 不变即不变) |
| 3 | code 有效期 | **长期** (只要档案不变, 一直能用) |
| 4 | code 绑定粒度 | **绑订单** (一申请人 + 一国家 = 一订单 = 一 code) |
| 5 | code 失效 | **插件要校验老 code** (后端 redeem 时比对 fingerprint, 不一致 409) |

---

## 🔥 这个设计的核心亮点:Code = 档案指纹

不是普通鉴权码。**Code 是档案内容 SHA-256 的索引**。

```
用户改了任一字段  →  fingerprint 雪崩  →  老 code 在插件 redeem 时被后端 409 拒掉
                                      →  强制用户回 Htex 拿新 code
```

**为什么这比"短码一次性"高级**:
- 短码 = 鉴权令牌 → 用户改档案后老令牌还能用 → 可能把老数据填到新表单 → 灾难
- 指纹 = 档案指纹 → 老 code 自动作废 → 用户必须回 Htex 拿新 → **零事故**

---

## 📋 跟 v0.1 相比, 改了什么

| 模块 | v0.1 | v0.2 |
|---|---|---|
| 数据交接 | App `postMessage` 同机直传 + 文件导入 | **后端发 12 位 code + 插件 redeem** |
| 跨设备 | 同机 + P2 扫码 E2E | **默认跨设备** (PC 装插件即可, 扫码 E2E 降级 P2) |
| 登录 DS-160 | 没设计 | **插件只提示, 用户自己登** |
| 档案版本控制 | 无 | **code = fingerprint, 自带版本控制** |
| 用户主动 rotate | 无 | **后端 `/code {force_rotate: true}`** + 黑名单 |
| Mapping 漂移 | DESIGN.md 标"必须加构建脚本" | **已实现** (`build-extension-mapping.mjs` 在跑) |

## 📋 v0.1 哪些**保留**(无需重写)

- `src/fillEngine.js` (278 行, 锚 label 定位 + 类型填值 + MutationObserver postback 跟填 + 逐项报告) — **全部沿用**
- `src/wayfinder.js` (84 行, 寻路定位 + 高亮 + 步骤检测) — **全部沿用**
- `src/journey.js` (49 行, 三步流程配置) — **全部沿用**
- `src/content-journey.js` (55 行, 寻路条 + 高亮编排) — **全部沿用**
- `src/mapping.js` (974 行, 自动生成的字段映射) — **全部沿用**
- `src/content-ds160.js` (187 行, 填充面板) — **小改**: 顶部加 order_id + fingerprint 显示 + 跨页进度徽标
- `test/mock-ds160.html` (66 行, 手动测试页) — **小改**: 加 "粘贴 code 模拟 redeem" 按钮

## 📋 v0.1 哪些**重写**

- `src/background.js` (33 行 → ~50 行): 新增 `HTEX_REDEEM_CODE` / `HTEX_GET_META` 消息
- `popup.html` / `popup.js` (44 行 → ~80 行): **改主路径** — 12 位 code 输入框 + Redeem 按钮, 取代文件导入
- `manifest.json` (33 行 → ~30 行): **移除** htexvisa.com 注入, **新增** api.htexvisa.com host
- `src/content-app.js` (22 行): **删除整个文件**

---

## 🛠️ 实现路线(等你拍板再开干)

### Phase 1: 后端 (1 天)

```
backend/
  app/
    models/order.py                     +6 列 (迁移脚本)
    core/ds160.py                       fingerprint + code + profile 加载 (~80 行)
    api/v2/ds160.py                     /code + /redeem 端点 (~150 行)
  scripts/migrate_ds160_code_fields.py  ALTER TABLE
  tests/unit/test_ds160.py              6 个 fingerprint/code 单测
  tests/api/test_ds160_api.py           9 个集成用例 (幂等 / 改档案 / revoke / 限频 / ...)
```

### Phase 2: 插件 (半天)

```
browser-extension/
  src/background.js                     重写 (HTEX_REDEEM_CODE 消息)
  popup.html                            重写 (code 输入框)
  popup.js                              重写 (调 /redeem)
  manifest.json                         更新 host_permissions
  src/content-app.js                    删除
  src/content-ds160.js                  小改 (加 meta 显示)
  test/mock-ds160.html                  小改 (加 mock redeem 按钮)
```

### Phase 3: Htex Web (1 小时)

```
frontend/web/src/views/OrderDetail.vue  + "去 DS-160 填表" 按钮
                                        + "重置 code" 按钮
                                        + code 展示 + 复制
                                        + "档案更新会自动换码" 提示
```

### Phase 4: 验证 (半天)

```
1. 起 dev 后端 + 跑 pytest
2. 真 Chrome 加载 extension
3. 手动跑 4 阶段 e2e (看 e2e-flow.mmd 流程图)
4. 改字段测试 ARCHIVE_CHANGED 红色 banner
```

**合计 2-3 天可上线 dev 环境**, 真 DS-160 官网验证需人工 (L1: 字段映射待对真表核对)。

---

## ⚠️ 已知债 & 风险

| 编号 | 描述 | 风险 | 优先级 |
|---|---|---|---|
| L1 | `DS160_VERIFIED_DATE = null` (字段映射未对真表核对) | 填的字段可能跟官网对不上 | **P0** |
| L2 | 预约站 URL 待核实 (各国 ustraveldocs/usvisa-info) | 寻路可能给错链接 | P1 |
| L3 | CI check `build-extension-mapping.mjs` 防漂移 | web 端改 mapping 后插件没同步 | **P0** |
| L4 | iframe 注入 (DS-160 部分页用 frame) | 面板挂掉 | P1 |
| L5 | 跨页累计进度 | 用户看不到"我填到第几页了" | P1 |
| L6 | 跨设备扫码 E2E | 默认跨设备已支持, 扫码降级 P2 | P2 |

---

## 🔐 安全模型一句话

- **Code 不可独立拿到档案** (要 code + order 存在 + fingerprint 匹配三层都过)
- **Code 不可暴力** (60 bits 熵 + 限频 60s/5 次)
- **Fingerprint 不可逆** (SHA-256 规范化快照, 无 PII 可还原)
- **后端零 PII 存储** (只存 code + fingerprint, 真档案在 order.applicants 既有表)
- **用户主动 rotate** (泄漏时一键黑名单)

---

## ❓ 接下来要不要我直接开干?

按你之前定的原则"不要反复问, 一直做到完", 我建议**直接进 Phase 1 后端**, 但有几个点你拍一下:

1. **Redis 实例是否已有**? 限频要用 Redis; 现有项目没用过的话要起一个
2. **Session 鉴权方式**? 复用 `Depends(get_current_user)` 还是要新加一个 chrome extension 鉴权? 我倾向复用现有 session, 因为是 Htex Web 调 /code 时用, 不是插件调
3. **`/redeem` 是否要加 hCaptcha / Cloudflare Turnstile**? 公开端点(无 session)通常加一道防 bot, 但加 UX 摩擦; 你业务量不大时先限频扛着
4. **L1 真表核对** 是不是你来核? 我不能替你对 ceac.state.gov, 但我可以**把核对流程写成一个 checklist 文档** (`DS160_VERIFICATION_CHECKLIST.md`), 你/运营拿着去核

你说"开干" 我就进 Phase 1 + 顺手把 checklist 写了。