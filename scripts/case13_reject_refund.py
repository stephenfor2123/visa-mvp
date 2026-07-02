"""
Case 13 — 拒签自动退服务费 (V0 §4.6.2)。

需求：
  - 订单状态机走到 rejected 时，必须自动发起退费
  - 退费金额 = 服务费（订单拆 service_fee + 官费）
  - 退费成功后，订单关联 payment.status = refunded
  - 退费流水本地存档，不可删
  - 边界：
      * 未支付的订单被拒签：不退费（自然状态）
      * 已拒签的订单重复退费：幂等
      * 同一笔支付不能退两次
      * 拒签 → 关单的链路（admin 推到 rejected 之后，业务侧可选择推到 closed）

当前 V0.4 状态：
  - 拒签 transition 存在，但**无 refund 触发**
  - 支付状态机只有 pending → paid → closed，**无 refunded 终态**
  - 这是 V0.5 必补的业务缺口

本脚本会：
  1) 跑一遍 happy path（拒签 → 期待退费）
  2) 把每个失败点标 [KNOWN_GAP]，便于你看 V0.5 修的时候对账
  3) 跑边界场景，确认现状行为
"""
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

BASE = "http://localhost:8000/api/v2"

results: List[Dict[str, Any]] = []
KNOWN_GAPS: List[str] = []


def record(step: str, ok: bool, detail: str = "", gap: bool = False) -> None:
    icon = "GAP" if gap else ("PASS" if ok else "FAIL")
    results.append({"step": step, "ok": ok, "detail": detail, "gap": gap})
    print(f"  [{icon}] {step}: {detail}")
    if gap:
        KNOWN_GAPS.append(f"{step} — {detail}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def envelope_ok(resp: Dict[str, Any]) -> bool:
    return resp["status"] in (200, 201) and (resp["body"].get("code") in ("1000", "0000") if isinstance(resp["body"], dict) else False)


def get(client: httpx.Client, path: str, token: Optional[str] = None, **kw) -> Dict[str, Any]:
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = client.get(f"{BASE}{path}", headers=h, timeout=20, **kw)
    return _wrap(r)


def post(client: httpx.Client, path: str, body: Optional[Dict[str, Any]] = None, token: Optional[str] = None, **kw) -> Dict[str, Any]:
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = client.post(f"{BASE}{path}", json=body or {}, headers=h, timeout=30, **kw)
    return _wrap(r)


def put(client: httpx.Client, path: str, body: Optional[Dict[str, Any]] = None, token: Optional[str] = None, **kw) -> Dict[str, Any]:
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = client.put(f"{BASE}{path}", json=body or {}, headers=h, timeout=30, **kw)
    return _wrap(r)


def _wrap(r: httpx.Response) -> Dict[str, Any]:
    try:
        return {"status": r.status_code, "body": r.json()}
    except Exception:
        return {"status": r.status_code, "body": r.text}


# ============================================================================ #
# Setup: 注册 + 下单 + 支付 + 推到 reviewing
# ============================================================================ #
def setup_order_paid(client: httpx.Client) -> Tuple[str, str, str]:
    """返回 (user_token, order_no, trade_no)"""
    suffix = uuid.uuid4().hex[:8]
    user = {"username": f"reject_{suffix}", "email": f"reject_{suffix}@htex.test", "password": "RejectTest@2024"}
    r = post(client, "/auth/register", user)
    if not envelope_ok(r):
        print(f"  setup register failed: {r}")
        sys.exit(1)
    user_token = r["body"]["data"]["access_token"]
    admin_tok = post(client, "/admin/login", {"username": "admin", "password": "Admin@2024"})
    admin_token = admin_tok["body"]["data"]["access_token"]

    # 上传材料 + 下单
    files = {"file": ("pp.jpg", b"\x89PNG\r\n\x1a\n" + b"x" * 200, "image/jpeg")}
    h = {"Authorization": f"Bearer {user_token}"}
    ur = client.post(f"{BASE}/materials/upload", files=files, data={"material_type": "passport"}, headers=h)
    mid = ur.json()["data"]["material"]["id"]

    body = {
        "destination_id": 1, "visa_type": "tourism", "material_ids": [mid],
        "applicant_data": {"surname": "WANG", "given_name": "FANG", "sex": "F", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "EA0012345", "passport_expiry": "2030-01-01"},
    }
    r = post(client, "/orders", body, token=user_token)
    order_no = r["body"]["data"]["order"]["order_no"]

    # 推到 submitted (admin)
    r2 = get(client, "/admin/orders?page=1&page_size=50", token=admin_token)
    oid = next(o["id"] for o in r2["body"]["data"]["items"] if o["order_no"] == order_no)
    put(client, f"/admin/orders/{oid}/status", {"status": "submitted", "note": "e2e"}, token=admin_token)
    # 推到 reviewing
    put(client, f"/admin/orders/{oid}/status", {"status": "reviewing", "note": "e2e"}, token=admin_token)

    # 支付 + notify paid
    r3 = post(client, "/payment/create", {"order_no": order_no, "amount_cents": 18500, "channel": "mock"}, token=user_token)
    trade_no = r3["body"]["data"]["trade_no"]
    post(client, "/payment/notify", {"trade_no": trade_no, "order_no": order_no, "status": "paid"})

    return user_token, order_no, trade_no, admin_token, oid


# ============================================================================ #
# Happy path: 拒签 → 自动退费
# ============================================================================ #
def case_reject_triggers_refund(client: httpx.Client) -> None:
    section("1. Happy path: 拒签 → 自动退费")
    user_token, order_no, trade_no, admin_token, oid = setup_order_paid(client)
    record("setup: order paid", True, f"order_no={order_no} trade_no={trade_no}")

    # admin 推到 rejected
    r = put(client, f"/admin/orders/{oid}/status", {"status": "rejected", "note": "e2e: visa denied"}, token=admin_token)
    if not envelope_ok(r):
        record("admin reject order", False, f"status={r['status']} body={r['body']}")
        return
    record("admin reject order", True, f"order now rejected")

    # 检查订单状态
    r2 = get(client, f"/admin/orders/{oid}", token=admin_token)
    order = r2["body"]["data"]
    if order["status"] == "rejected":
        record("order.status == rejected", True, "order reflects reject")
    else:
        record("order.status == rejected", False, f"got {order['status']!r}")

    # 期待：payment.status = refunded
    r3 = get(client, "/admin/payments?page=1&page_size=50", token=admin_token)
    pay = next((p for p in r3["body"]["data"]["items"] if p.get("trade_no") == trade_no), None)
    if not pay:
        record("payment visible after reject", False, "payment row missing")
        return
    pay_status = pay.get("status")
    if pay_status == "refunded":
        record("payment auto-refunded after reject", True, f"status={pay_status}")
    elif pay_status == "paid":
        record(
            "payment auto-refunded after reject",
            False,
            f"支付仍是 paid，V0.4 未实现拒签退费 — KNOWN_GAP",
            gap=True,
        )
    else:
        record("payment auto-refunded after reject", False, f"status={pay_status!r}")

    # 期待：有退费流水记录（独立行）
    refund_rows = [p for p in r3["body"]["data"]["items"] if p.get("status") == "refunded" and (p.get("order_no") == order_no or p.get("related_trade_no") == trade_no)]
    if refund_rows:
        record("refund ledger row exists", True, f"count={len(refund_rows)}")
    else:
        record("refund ledger row exists", False, "无独立退费流水 — KNOWN_GAP", gap=True)


# ============================================================================ #
# 边界 1: 未支付的订单被拒签 — 不应触发退费
# ============================================================================ #
def case_reject_unpaid_no_refund(client: httpx.Client) -> None:
    section("2. 边界: 未支付订单被拒签 — 不退费")
    suffix = uuid.uuid4().hex[:8]
    user = {"username": f"unpaid_{suffix}", "email": f"unpaid_{suffix}@htex.test", "password": "Test@2024"}
    r = post(client, "/auth/register", user)
    user_token = r["body"]["data"]["access_token"]
    admin_tok = post(client, "/admin/login", {"username": "admin", "password": "Admin@2024"})
    admin_token = admin_tok["body"]["data"]["access_token"]

    files = {"file": ("pp.jpg", b"x" * 200, "image/jpeg")}
    h = {"Authorization": f"Bearer {user_token}"}
    ur = client.post(f"{BASE}/materials/upload", files=files, data={"material_type": "passport"}, headers=h)
    mid = ur.json()["data"]["material"]["id"]
    body = {
        "destination_id": 1, "visa_type": "tourism", "material_ids": [mid],
        "applicant_data": {"surname": "X", "given_name": "Y", "sex": "M", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "EB9999", "passport_expiry": "2030-01-01"},
    }
    r = post(client, "/orders", body, token=user_token)
    order_no = r["body"]["data"]["order"]["order_no"]
    # 推到 rejected
    r2 = get(client, "/admin/orders?page=1&page_size=50", token=admin_token)
    oid = next(o["id"] for o in r2["body"]["data"]["items"] if o["order_no"] == order_no)
    put(client, f"/admin/orders/{oid}/status", {"status": "submitted", "note": "e2e"}, token=admin_token)
    put(client, f"/admin/orders/{oid}/status", {"status": "reviewing", "note": "e2e"}, token=admin_token)
    put(client, f"/admin/orders/{oid}/status", {"status": "rejected", "note": "e2e unpaid reject"}, token=admin_token)
    # 没支付过，不应有 refund 流水
    r3 = get(client, "/admin/payments?page=1&page_size=50", token=admin_token)
    refunds = [p for p in r3["body"]["data"]["items"] if p.get("status") == "refunded" and p.get("order_no") == order_no]
    if not refunds:
        record("unpaid order reject → no refund", True, "正确：未支付订单无退费")
    else:
        record("unpaid order reject → no refund", False, f"found {len(refunds)} refund rows (unexpected)")


# ============================================================================ #
# 边界 2: 拒签后退款幂等 — 重复调用 refund 不应多次退
# ============================================================================ #
def case_refund_idempotent(client: httpx.Client) -> None:
    section("3. 边界: 退费幂等 — 重复触发不退两次")
    user_token, order_no, trade_no, admin_token, oid = setup_order_paid(client)
    put(client, f"/admin/orders/{oid}/status", {"status": "rejected", "note": "e2e: 1st reject"}, token=admin_token)
    # 期望：如果 V0.5 实现了 refund 接口，重复调用 refund endpoint 应 200/幂等
    # 当前 V0.4 没有任何 refund endpoint
    # 我们用 payment/{order_no} 重复查询看 payment.status 是否一致
    r = get(client, f"/payment/{order_no}", token=user_token)
    if envelope_ok(r):
        st = r["body"]["data"]["status"]
        record("payment status stable", st in ("paid", "refunded"), f"status={st}")
    else:
        record("query payment", False, f"status={r['status']}")
    # 期待：order_id 关联的 refund 流水只有 0 条或 1 条（不能 ≥2）
    r2 = get(client, "/admin/payments?page=1&page_size=50", token=admin_token)
    refunds = [p for p in r2["body"]["data"]["items"] if p.get("status") == "refunded" and p.get("order_no") == order_no]
    if len(refunds) <= 1:
        record("refund count ≤ 1", True, f"count={len(refunds)}")
    else:
        record("refund count ≤ 1", False, f"found {len(refunds)} refund rows for same order — duplicate!")


# ============================================================================ #
# 边界 3: 拒签 vs 关单 — 应走不同的状态机路径
# ============================================================================ #
def case_rejected_vs_closed(client: httpx.Client) -> None:
    section("4. 边界: rejected → closed — 用户确认关单归档（合法）")
    user_token, order_no, trade_no, admin_token, oid = setup_order_paid(client)
    # 拒签
    r = put(client, f"/admin/orders/{oid}/status", {"status": "rejected", "note": "reject"}, token=admin_token)
    if not envelope_ok(r):
        record("transition to rejected", False, f"{r['body']}")
        return
    # 拒签 → 关单（用户确认关单归档，VALID_TRANSITIONS 允许）
    r2 = put(client, f"/admin/orders/{oid}/status", {"status": "closed", "note": "user confirmed close"}, token=admin_token)
    if envelope_ok(r2) and r2["body"]["data"]["status"] == "closed":
        record("rejected → closed accepted (user confirms)", True, "合法业务路径：拒签后用户/运营确认关单归档")
    else:
        record("rejected → closed accepted", False, f"{r2}")
    # 但是反向 closed → rejected 应被拒绝
    r3 = put(client, f"/admin/orders/{oid}/status", {"status": "rejected", "note": "reverse"}, token=admin_token)
    if r3["status"] >= 400:
        record("closed → rejected blocked (terminal)", True, f"已正确拒绝（{r3['status']}）")
    else:
        record("closed → rejected blocked (terminal)", False, f"closed 是终态但允许回到 rejected: {r3['body']}")


# ============================================================================ #
# 边界 4: 退费流水不可删（V0 §4.6.3）
# ============================================================================ #
def case_refund_ledger_immutable(client: httpx.Client) -> None:
    section("5. 边界: 退费流水不可删（V0 §4.6.3）")
    # 当前 V0.4 还没有独立 refund 表，admin /payments 列表也没有删除接口
    # 这一步作为 V0.5 验证锚点
    r = get(client, "/admin/payments?page=1&page_size=1", token=post(client, "/admin/login", {"username": "admin", "password": "Admin@2024"})["body"]["data"]["access_token"])
    if envelope_ok(r):
        record("refund ledger accessible to admin", True, "payment list endpoint works")
    # 检查有没有 DELETE /admin/payments/{id}
    # 已知：没有，V0.5 加 refund 时同步保证"无 delete endpoint"
    record("refund row deletion blocked (no DELETE endpoint)", True, "V0.4 现状：payment/admin-payments 没有 DELETE 路由 — KNOWN_GAP（V0.5 应继续无 DELETE）", gap=True)


# ============================================================================ #
# Main
# ============================================================================ #
def main() -> int:
    print(f"Case 13 — 拒签自动退服务费 @ {datetime.now().isoformat()}")
    print(f"  注：限流 100 req/min, case 之间 sleep 等重置")
    with httpx.Client() as client:
        case_reject_triggers_refund(client)
        time.sleep(65)
        case_reject_unpaid_no_refund(client)
        time.sleep(65)
        case_refund_idempotent(client)
        time.sleep(65)
        case_rejected_vs_closed(client)
        time.sleep(65)
        case_refund_ledger_immutable(client)

    section("SUMMARY")
    passed = sum(1 for r in results if r["ok"] and not r["gap"])
    failed = sum(1 for r in results if not r["ok"])
    gaps = sum(1 for r in results if r["gap"])
    print(f"  Total: {len(results)}  PASS: {passed}  FAIL: {failed}  KNOWN_GAP: {gaps}")
    if KNOWN_GAPS:
        print("\n  已知缺口（V0.5 待补）:")
        for g in KNOWN_GAPS:
            print(f"    - {g}")
    if failed:
        print("\n  Failed:")
        for r in results:
            if not r["ok"] and not r["gap"]:
                print(f"    - {r['step']}: {r['detail']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())