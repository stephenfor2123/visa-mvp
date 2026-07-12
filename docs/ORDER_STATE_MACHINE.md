# Order State Machine — Htex Visa (v2, 2026-07)

## 一、订单主轨（`order.status`）

```
created ──支付──→ paid ──AI诊断完成──→ completed
   │
   └──1h未付 / 用户取消──→ cancelled
```

| 状态 | 含义 | 触发 |
|------|------|------|
| `created` | 新订单，待支付（1h 锁定） | 填表完成创建订单 |
| `paid` | 已支付，待 AI 诊断 | 支付回调 |
| `completed` | **Htex 服务完成**（AI 诊断完成） | `POST /orders/{no}/diagnosis-complete` |
| `cancelled` | 已取消 | 超时未付 / 用户取消 |

**不判断下签。** 旧状态 `submitted/reviewing/approved/rejected` 仅用于历史数据。

## 二、官网提交里程碑（不改主状态）

| 字段 | 说明 |
|------|------|
| `portal_submitted_at` | 用户确认已在使馆/签证中心官网提交 |
| `portal_submitted_source` | `extension` \| `user` \| `admin` |

通道：
- 插件（US DS-160）→ `POST /api/v2/ds160/portal-submitted`
- 用户按钮 → `POST /api/v2/orders/{no}/portal-submitted`
- Admin → `PUT /api/v2/admin/orders/{id}/portal-submitted`

订单已是 `completed` 也可补记；用户不确认也不卡死。

## 三、退款副轨（`refund_status`）

```
none → pending → approved → completed
         ↘ rejected
              approved → failed → (重试)
```

| 状态 | 含义 |
|------|------|
| `pending` | 用户申请，待审核 |
| `approved` | Admin 同意 |
| `completed` | 退款到账 |
| `rejected` | 审核驳回 |
| `failed` | 打款失败 |

**不改变** `order.status`（服务已完成与退款可并存）。

## 四、运营关注（`GET /admin/orders/attention/counts`）

- `payment_expiring_soon` — 即将超时未付
- `paid_awaiting_diagnosis` — 已付未诊断
- `completed_awaiting_portal` — 已完成未确认官网提交
- `refund_pending` / `refund_failed`

## 五、关键字段

| 字段 | 用途 |
|------|------|
| `locked_until` | 创建后 1h 支付截止 |
| `paid_at` | 支付时间 |
| `diagnosis_completed_at` | AI 诊断完成 |
| `completed_at` | 服务完成时间 |
| `refund_*` | 退款流程 |

## 六、相关文件

- `backend/app/models/order.py` — `VALID_TRANSITIONS`
- `backend/app/services/order_service.py` — 生命周期方法
- `backend/app/services/payment_provider.py` — 支付 → `paid`
- `frontend/web/src/composables/useOrderUserStatus.js` — 用户展示态
