# 产品范围

> **决策日期**: 2026-07-11

## 业务定位（纠正版）

| 维度 | 说明 |
|------|------|
| **客户市场** | 越南、印尼海外用户（Web 端，非微信小程序） |
| **办理的签证** | 美国、申根、英国、澳大利亚等（目的地国家**不变**） |
| **语言** | zh-CN / en / **id** / **vi** 四语覆盖 |

简单说：**在越南/印尼获客，帮客户办美签、申根、英签、澳签**。

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
