# 产品范围

> **决策日期**: 2026-07-11  
> **口径复核**: 2026-07-20

## 业务定位（纠正版）

| 维度 | 说明 |
|------|------|
| **客户市场** | 越南、印尼海外用户（Web 端，非微信小程序）——护照/国籍 |
| **办理的签证（目的地）** | **仅**美国、英国、澳大利亚、申根（代表国 DE / FR） |
| **明确不办** | 印尼签证、越南签证、日本、加拿大、新加坡、新西兰等 |
| **语言** | zh-CN / en / **id** / **vi** 四语覆盖 |

简单说：**在越南/印尼获客，帮客户办美签、申根、英签、澳签**。  
印尼 / 越南出现在国籍下拉、i18n、合规文案里是正常的；**绝不能**出现在「选目的地 / 数据诊断 / 申请」的可选签证国列表里。

## 当前关闭的功能（后期再开）

| 功能 | 后端 | 前端 | 说明 |
|------|------|------|------|
| 微信小程序 | — | ⏸ | 见 `frontend/miniprogram/PAUSED.md` |
| RPA 自动递交 | `FEATURE_RPA_ENABLED=0` | `VITE_FEATURE_RPA=false` | `/rpa/*` 路由重定向 |
| 拒签险 | `FEATURE_INSURANCE_ENABLED=0` | `VITE_FEATURE_INSURANCE=false` | `/insurance/*` 不注册 |

## 用户主流程（当前）

```
注册/登录 → 选目的地（美/申根/英/澳）→ 材料向导 → 填表 → 提交
    → 支付 → 订单详情（人工跟进，RPA 关闭期间）
```

## 代码护栏

| 位置 | 作用 |
|------|------|
| `backend/app/core/product_scope.py` | 目的地白名单 |
| `backend/app/api/v2/destinations.py` | 公开列表只返回产品线 |
| `frontend/web/src/api/destinations.js` | 前端二次过滤 |
| Alembic `0027_product_destination_scope` | DB `enabled` 对齐 |

## 配置

```bash
# backend/.env
FEATURE_RPA_ENABLED=0
FEATURE_INSURANCE_ENABLED=0

# frontend/web/.env
VITE_FEATURE_RPA=false
VITE_FEATURE_INSURANCE=false
```

恢复 RPA / 保险时把上述开关改为 `1` / `true` 并重启。
