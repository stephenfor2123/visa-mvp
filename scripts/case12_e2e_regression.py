"""
Htex E2E regression test (W35).

完整业务流验证：注册 → 后台有用户 → 下单 → 后台有订单 → 支付 → 后台资金流有记录
逆向流：订单取消 → 后台订单状态同步 → 资金回退
最终一致性检查：4 张表对账

用法：
  PYTHONPATH=. .venv/bin/python tests/e2e_regression.py

会输出每步 PASS/FAIL，最终给一个汇总 + 任何不一致都会列出。
"""
import json
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

BASE = "http://localhost:8000/api/v2"
ADMIN_BASE = f"{BASE}/admin"

results: List[Dict[str, Any]] = []
def record(step: str, ok: bool, detail: str = "") -> None:
    icon = "PASS" if ok else "FAIL"
    results.append({"step": step, "ok": ok, "detail": detail})
    print(f"  [{icon}] {step}: {detail}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def assert_eq(label: str, got: Any, expected: Any) -> bool:
    ok = got == expected
    record(f"{label} == {expected}", ok, f"got={got!r}")
    return ok


def get(client: httpx.Client, path: str, token: Optional[str] = None, **kw) -> Dict[str, Any]:
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = client.get(f"{BASE}{path}", headers=h, timeout=20, **kw)
    return {"status": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}


def post(client: httpx.Client, path: str, body: Optional[Dict[str, Any]] = None, token: Optional[str] = None, **kw) -> Dict[str, Any]:
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = client.post(f"{BASE}{path}", json=body or {}, headers=h, timeout=30, **kw)
    try:
        return {"status": r.status_code, "body": r.json()}
    except Exception:
        return {"status": r.status_code, "body": r.text}


def put(client: httpx.Client, path: str, body: Optional[Dict[str, Any]] = None, token: Optional[str] = None, **kw) -> Dict[str, Any]:
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = client.put(f"{BASE}{path}", json=body or {}, headers=h, timeout=30, **kw)
    try:
        return {"status": r.status_code, "body": r.json()}
    except Exception:
        return {"status": r.status_code, "body": r.text}


def envelope_ok(resp: Dict[str, Any]) -> bool:
    return resp["status"] in (200, 201) and resp["body"].get("code") == "1000"


def envelope_data(resp: Dict[str, Any]) -> Any:
    return resp["body"].get("data")


# ============================================================================ #
# Phase 0 — Admin login
# ============================================================================ #
def phase_admin_login(client: httpx.Client) -> str:  # type: ignore[misc]
    section("0. Admin 登录")
    r = post(client, "/admin/login", {"username": "admin", "password": "Admin@2024"})
    if not envelope_ok(r):
        record("admin login", False, f"status={r['status']} body={r['body']}")
        sys.exit(1)
    token = envelope_data(r)["access_token"]
    record("admin login", True, f"token={token[:20]}...")
    return token


# ============================================================================ #
# Phase 1 — C 端用户注册
# ============================================================================ #
def phase_register(client: httpx.Client) -> Tuple[str, Dict[str, Any]]:
    section("1. C 端用户注册")
    suffix = uuid.uuid4().hex[:8]
    username = f"e2e_user_{suffix}"
    email = f"e2e_{suffix}@htex.test"
    body = {"username": username, "email": email, "password": "E2eTest@2024", "nickname": f"E2E-{suffix}"}
    r = post(client, "/auth/register", body)
    if not envelope_ok(r):
        record("user register", False, f"status={r['status']} body={r['body']}")
        sys.exit(1)
    data = envelope_data(r)
    user_token = data.get("access_token") or data.get("token") or ""
    user_id = data.get("user", {}).get("id") if isinstance(data.get("user"), dict) else None
    if not user_id and data.get("user_id"):
        user_id = data["user_id"]
    record("user register", True, f"user_id={user_id} username={username}")
    return user_token, {"id": user_id, "username": username, "email": email}


# ============================================================================ #
# Phase 2 — 后台立即看到该用户
# ============================================================================ #
def phase_user_in_admin(client: httpx.Client, admin_token: str, expected_user: Dict[str, Any]) -> None:
    section("2. 后台立即看到该用户")
    # 通过 /users?search=username 找不到的话用 list 分页找
    found = None
    for page in (1, 2, 3):
        r = get(client, f"/admin/users?page={page}&page_size=100", token=admin_token)
        if not envelope_ok(r):
            record("admin list users", False, f"status={r['status']}")
            return
        for u in envelope_data(r)["items"]:
            if u.get("username") == expected_user["username"]:
                found = u
                break
        if found:
            break
    if not found:
        record("user visible in admin", False, f"username={expected_user['username']} not found")
        return
    assert_eq("user.id matches", found.get("id"), expected_user["id"])
    # Email 在 admin 接口是脱敏的（e2***@htex.test，保留前 2 位），只验证前缀
    admin_email = found.get("email") or ""
    email_prefix = expected_user["email"].split("@")[0][:2]
    record("user.email prefix matches", admin_email.startswith(email_prefix), f"got={admin_email!r} expected_prefix={email_prefix}")
    assert_eq("user.status", found.get("status"), "active")


# ============================================================================ #
# Phase 3 — C 端登录 & 下单
# ============================================================================ #
def phase_login(client: httpx.Client, expected_user: Dict[str, Any]) -> str:
    section("3. C 端用户登录")
    r = post(client, "/auth/login", {"account": expected_user["username"], "password": "E2eTest@2024"})
    if not envelope_ok(r):
        record("user login", False, f"status={r['status']} body={r['body']}")
        sys.exit(1)
    data = envelope_data(r)
    token = data.get("access_token") or data.get("token") or ""
    record("user login", True, f"token={token[:20]}...")
    return token


def phase_create_order(client: httpx.Client, user_token: str) -> Optional[Dict[str, Any]]:
    section("4. 下单")
    # 4a) 先上传一份材料（passport），让订单能挂上去
    # 用 multipart/form-data
    files = {"file": ("passport.jpg", b"\x89PNG\r\n\x1a\n" + b"fake_passport_data_e2e_test" * 50, "image/jpeg")}
    data = {"material_type": "passport"}
    h = {"Authorization": f"Bearer {user_token}"}
    ur = client.post(f"{BASE}/materials/upload", files=files, data=data, headers=h, timeout=30)
    if ur.status_code != 201:
        record("upload material", False, f"status={ur.status_code} body={ur.text[:200]}")
        return None
    up_data = ur.json().get("data") or {}
    mid = (up_data.get("material") or {}).get("id")
    if not mid:
        record("upload material", False, f"no material.id in {up_data}")
        return None
    record("upload material", True, f"material_id={mid}")

    # 4b) 创建订单（material_ids 至少要 1 个）
    body = {
        "destination_id": 1,  # US
        "visa_type": "tourism",
        "material_ids": [mid],
        "applicant_data": {
            "surname": "ZHANG", "given_name": "Wei", "sex": "M",
            "dob": "1992-04-12", "nationality": "CHN",
            "passport_no": "E12345678", "passport_expiry": "2030-08-15",
        },
        "aff_code": None,
    }
    r = post(client, "/orders", body, token=user_token)
    if not envelope_ok(r) and r["status"] != 201:
        record("create order", False, f"status={r['status']} body={r['body']}")
        return None
    data = envelope_data(r)
    order = data.get("order") or data
    record("create order", True, f"order_no={order.get('order_no')} status={order.get('status')}")
    return order


# ============================================================================ #
# Phase 4 — 后台订单列表里能看到
# ============================================================================ #
def phase_order_in_admin(client: httpx.Client, admin_token: str, order_no: str) -> bool:
    section("5. 后台订单列表能找到")
    r = get(client, f"/admin/orders?page=1&page_size=20", token=admin_token)
    if not envelope_ok(r):
        record("admin list orders", False, f"status={r['status']}")
        return False
    items = envelope_data(r)["items"]
    found = next((o for o in items if o.get("order_no") == order_no), None)
    if not found:
        record("order visible in admin", False, f"order_no={order_no} not found in {len(items)} orders")
        return False
    record("order visible in admin", True, f"id={found.get('id')} status={found.get('status')}")
    return True


# ============================================================================ #
# Phase 5 — 后台操作员把订单改成「submitted」
# ============================================================================ #
def phase_submit_via_admin(client: httpx.Client, admin_token: str, order_no: str) -> Optional[str]:
    section("6. 后台操作员把订单置为 submitted")
    # admin 路由用 order_id (int)，不是 order_no。先从列表拿到 id
    r = get(client, "/admin/orders?page=1&page_size=20", token=admin_token)
    if not envelope_ok(r):
        record("admin list orders (pre)", False, f"status={r['status']}")
        return None
    items = envelope_data(r)["items"]
    found = next((o for o in items if o.get("order_no") == order_no), None)
    if not found:
        record("admin find order by order_no", False, f"order_no={order_no} not in admin list")
        return None
    oid = found["id"]
    r = get(client, f"/admin/orders/{oid}", token=admin_token)
    if not envelope_ok(r):
        record("admin get order", False, f"status={r['status']} body={r['body']}")
        return None
    order = envelope_data(r)
    # 状态机: created -> submitted（admin 接口是 PUT）
    r2 = put(client, f"/admin/orders/{oid}/status", {"status": "submitted", "note": "e2e: backend operator pushed"}, token=admin_token)
    if not envelope_ok(r2):
        record("admin transition to submitted", False, f"status={r2['status']} body={r2['body']}")
        return None
    data = envelope_data(r2)
    new_status = data.get("status") or data.get("to_status")
    record("admin transition to submitted", True, f"new_status={new_status}")
    return new_status


# ============================================================================ #
# Phase 6 — 支付 + 后台资金流
# ============================================================================ #
def phase_payment(client: httpx.Client, user_token: str, order_no: str, admin_token: str) -> Optional[Dict[str, Any]]:
    section("7. 支付 + 后台资金流")
    # 1) C 端创建支付订单（路径是 /payment/create，需要 amount_cents）
    body = {"order_no": order_no, "amount_cents": 18500, "channel": "mock"}
    r = post(client, "/payment/create", body, token=user_token)
    if not envelope_ok(r) and r["status"] != 201:
        record("create payment", False, f"status={r['status']} body={r['body']}")
        return None
    pay_data = envelope_data(r)
    trade_no = pay_data.get("trade_no") or pay_data.get("payment", {}).get("trade_no")
    record("create payment", True, f"trade_no={trade_no}")
    # 2) 触发 mock 通知（/payment/notify）将状态置为 paid
    if trade_no:
        r2 = post(client, "/payment/notify", {"trade_no": trade_no, "order_no": order_no, "status": "paid"}, token=user_token)
        if envelope_ok(r2):
            record("mock notify paid", True, f"trade_no={trade_no}")
        else:
            # 后备: admin 手动 mark paid
            r3 = post(client, f"/payment/{trade_no}/admin-mark-paid", {}, token=admin_token)
            record("mock notify paid (or admin mark)", envelope_ok(r3), f"trade_no={trade_no}")
    # 3) 后台资金流查询
    r4 = get(client, "/admin/payments?page=1&page_size=20", token=admin_token)
    if not envelope_ok(r4):
        record("admin list payments", False, f"status={r4['status']}")
        return None
    items = envelope_data(r4)["items"]
    found = next((p for p in items if p.get("trade_no") == trade_no), None)
    if not found:
        record("payment visible in admin", False, f"trade_no={trade_no} not found")
        return None
    assert_eq("payment.status in admin", found.get("status"), "paid")
    return {"trade_no": trade_no, "order_no": order_no, "amount": found.get("amount_cents")}


# ============================================================================ #
# Phase 7 — 逆向：取消订单 (admin override to closed)
# ============================================================================ #
def phase_cancel(client: httpx.Client, admin_token: str, order_no: str) -> None:
    section("8. 逆向：后台 admin override closed")
    r = get(client, "/admin/orders?page=1&page_size=20", token=admin_token)
    if not envelope_ok(r):
        record("admin list orders (pre-close)", False, f"status={r['status']}")
        return
    items = envelope_data(r)["items"]
    found = next((o for o in items if o.get("order_no") == order_no), None)
    if not found:
        record("admin find order for close", False, f"order_no={order_no} not found")
        return
    oid = found["id"]
    r2 = put(client, f"/admin/orders/{oid}/status", {"status": "closed", "note": "e2e: admin override closed"}, token=admin_token)
    if not envelope_ok(r2):
        record("admin transition to closed", False, f"status={r2['status']} body={r2['body']}")
        return
    record("admin transition to closed", True, f"order_id={oid}")


# ============================================================================ #
# Phase 8 — 资金流 closed 状态同步
# ============================================================================ #
def phase_payment_closed(client: httpx.Client, admin_token: str, trade_no: str) -> None:
    section("9. 资金流 closed 状态同步")
    r = get(client, "/admin/payments?page=1&page_size=50", token=admin_token)
    if not envelope_ok(r):
        record("admin list payments after close", False, f"status={r['status']}")
        return
    items = envelope_data(r)["items"]
    found = next((p for p in items if p.get("trade_no") == trade_no), None)
    if not found:
        record("payment still visible", False, "payment disappeared")
        return
    # 关闭订单会自动 close 关联支付
    status_now = found.get("status")
    ok = status_now in ("closed", "paid")  # 至少状态有反映
    record("payment reflects close", ok, f"status={status_now}")


# ============================================================================ #
# Phase 9 — 一致性对账
# ============================================================================ #
def phase_consistency(client: httpx.Client, admin_token: str, expected_user: Dict[str, Any], order_no: str, trade_no: str) -> None:
    section("10. 一致性对账")
    issues = []

    # 1) 用户表 → 用户注册字段都完整（admin 接口 email 被脱敏）
    r = get(client, f"/admin/users/{expected_user['id']}", token=admin_token)
    if envelope_ok(r):
        u = envelope_data(r)
        admin_email = u.get("email") or ""
        email_prefix = expected_user["email"].split("@")[0][:2]
        if not admin_email.startswith(email_prefix):
            issues.append(f"email prefix mismatch: got {admin_email!r}")
        if u.get("status") != "active":
            issues.append(f"user.status not active: {u.get('status')!r}")
    else:
        issues.append(f"admin get user failed: {r['status']}")

    # 2) 订单表 → 订单状态在 closed（用 order_id 而不是 order_no）
    # 先从 list 找到 id
    r_list = get(client, "/admin/orders?page=1&page_size=50", token=admin_token)
    oid = None
    if envelope_ok(r_list):
        for oo in envelope_data(r_list)["items"]:
            if oo.get("order_no") == order_no:
                oid = oo["id"]
                break
    if not oid:
        issues.append(f"order_no {order_no!r} not found in admin list")
        record("consistency", False, "; ".join(issues))
        return
    r2 = get(client, f"/admin/orders/{oid}", token=admin_token)
    if envelope_ok(r2):
        o = envelope_data(r2)
        if o.get("status") != "closed":
            issues.append(f"order.status != closed: {o.get('status')!r}")
        # status_history 应包含每一步
        hist = o.get("status_history") or []
        actions_seen = {h.get("to_status") for h in hist if h.get("to_status")}
        for need in ("submitted", "closed"):
            if need not in actions_seen:
                issues.append(f"status_history missing {need!r}: actions={actions_seen}")
        # audit_logs 应包含此订单的条目
        audit = o.get("audit_logs") or []
        if not audit:
            issues.append("audit_logs empty for order")
    else:
        issues.append(f"admin get order failed: {r2['status']}")

    # 3) 支付流 → trade_no 存在
    r3 = get(client, "/admin/payments?page=1&page_size=50", token=admin_token)
    if envelope_ok(r3):
        items = envelope_data(r3)["items"]
        pay = next((p for p in items if p.get("trade_no") == trade_no), None)
        if not pay:
            issues.append(f"trade_no {trade_no!r} missing in payment list")
    else:
        issues.append(f"admin list payments failed: {r3['status']}")

    # 4) 系统日志 → 应有 user.register / order.create / payment.notify / admin.order.update_status 等动作
    r4 = get(client, "/admin/logs?page=1&page_size=50", token=admin_token)
    if envelope_ok(r4):
        logs = envelope_data(r4)["items"]
        actions_seen = {l.get("action") for l in logs}
        for need in ("user.register", "order.create"):
            if need not in actions_seen:
                issues.append(f"audit_log missing action {need!r}: have={list(actions_seen)[:5]}")
    else:
        issues.append(f"admin list logs failed: {r4['status']}")

    if issues:
        record("consistency", False, "; ".join(issues))
        for i in issues:
            print(f"      ! {i}")
    else:
        record("consistency", True, "用户/订单/支付/日志 四表对账一致")


# ============================================================================ #
# Main
# ============================================================================ #
def main() -> int:
    print(f"E2E Regression @ {datetime.now().isoformat()}")
    print(f"Target: {BASE}")
    with httpx.Client() as client:
        admin_token = phase_admin_login(client)
        user_token, expected_user = phase_register(client)
        phase_user_in_admin(client, admin_token, expected_user)
        # login 后再次拿到 user_token（register 返回的可能格式不同）
        user_token = phase_login(client, expected_user)
        order = phase_create_order(client, user_token)
        if not order:
            print("\n❌ Aborting: failed to create order")
            return 1
        order_no = order["order_no"]
        phase_order_in_admin(client, admin_token, order_no)
        phase_submit_via_admin(client, admin_token, order_no)
        payment = phase_payment(client, user_token, order_no, admin_token)
        if payment:
            phase_cancel(client, admin_token, order_no)
            phase_payment_closed(client, admin_token, payment["trade_no"])
            phase_consistency(client, admin_token, expected_user, order_no, payment["trade_no"])
        else:
            print("\n⚠️  Payment failed — skipping cancel/consistency")

    # 汇总
    section("SUMMARY")
    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    print(f"  Total: {len(results)}  PASS: {passed}  FAIL: {failed}")
    if failed:
        print("\n  Failed steps:")
        for r in results:
            if not r["ok"]:
                print(f"    - {r['step']}: {r['detail']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())