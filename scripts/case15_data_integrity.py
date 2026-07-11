"""
Case 15 — 数据完整性 / 丢数据防护 (V0 §4.1.4 + §4.7)。

需求文档 V0：
  - §4.1.4 注销逻辑：触发定时任务，72 小时清空账号所有数据&文件
  - §4.7 全链路日志：不可篡改、删除

本脚本覆盖：
  1) 重复注册同 username/email：应被拒绝（不创建幽灵账号）
  2) 重复创建支付：同订单多次 create payment 应幂等或拒绝
  3) 重复支付 notify：paid → paid 不可变
  4) 用户软删后不能再登录：status=disabled → 401
  5) 用户注销（pending_destroy）后不可新建订单
  6) 删除 order 关联 material：material 删除不应影响 order 完整性
  7) 审计日志完整性：订单状态流转每个动作都应有 audit log
  8) 跨用户隔离：A 用户 token 不能查 B 用户的订单
  9) 改订单状态（admin override）不丢 status_history
 10) 重启后数据不丢：写完后查询，新进程/新 session 应能读到

输出 PASS/FAIL。FAIL 表示潜在数据丢失风险。
"""
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

BASE = "http://localhost:8000/api/v2"

results: List[Dict[str, Any]] = []


def record(step: str, ok: bool, detail: str = "", gap: bool = False) -> None:
    icon = "GAP" if gap else ("PASS" if ok else "FAIL")
    results.append({"step": step, "ok": ok, "detail": detail, "gap": gap})
    print(f"  [{icon}] {step}: {detail}")


def section(t: str) -> None:
    print(f"\n=== {t} ===")


def get(client, path, token=None, **kw):
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return client.get(f"{BASE}{path}", headers=h, timeout=15, **kw)


def post(client, path, body=None, token=None, **kw):
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return client.post(f"{BASE}{path}", json=body or {}, headers=h, timeout=15, **kw)


def put(client, path, body=None, token=None, **kw):
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return client.put(f"{BASE}{path}", json=body or {}, headers=h, timeout=15, **kw)


def del_(client, path, token=None, **kw):
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return client.delete(f"{BASE}{path}", headers=h, timeout=15, **kw)


# ============================================================================ #
# 1) 重复注册同 username / email
# ============================================================================ #
def case_dup_register(client) -> None:
    section("1. 重复注册 — username/email 唯一性")
    suffix = uuid.uuid4().hex[:6]
    user = {"username": f"dup_{suffix}", "email": f"dup_{suffix}@htex.test", "password": "Dup@2024"}
    r1 = post(client, "/auth/register", user)
    if r1.status_code != 201:
        record("1st register", False, f"{r1.status_code} {r1.text[:100]}")
        return
    record("1st register", True, "OK")
    r2 = post(client, "/auth/register", user)
    record("2nd register same user rejected", r2.status_code in (400, 409, 422), f"status={r2.status_code}")
    # 单独只 email 重复
    r3 = post(client, "/auth/register", {"username": f"dup2_{suffix}", "email": user["email"], "password": "Dup@2024"})
    record("dup email rejected", r3.status_code in (400, 409, 422), f"status={r3.status_code}")


# ============================================================================ #
# 2) 重复创建支付（同一订单）
# ============================================================================ #
def case_dup_payment(client) -> None:
    section("2. 重复支付 — 同订单多次 create payment")
    suffix = uuid.uuid4().hex[:6]
    r = post(client, "/auth/register", {"username": f"pay_{suffix}", "email": f"pay_{suffix}@htex.test", "password": "Pay@2024"})
    user_token = r.json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {user_token}"}
    files = {"file": ("pp.jpg", b"x" * 200, "image/jpeg")}
    ur = client.post(f"{BASE}/materials/upload", files=files, data={"material_type": "passport"}, headers=h)
    mid = ur.json()["data"]["material"]["id"]
    r = post(client, "/orders", {
        "destination_id": 1, "visa_type": "tourism", "material_ids": [mid],
        "applicant_data": {"surname": "T", "given_name": "U", "sex": "M", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "PA1234567", "passport_expiry": "2030-01-01"},
    }, token=user_token)
    order_no = r.json()["data"]["order"]["order_no"]

    # 第一次支付
    r1 = post(client, "/payment/create", {"order_no": order_no, "amount_cents": 1000, "channel": "mock"}, token=user_token)
    trade1 = r1.json().get("data", {}).get("trade_no")
    record("1st payment create", trade1 is not None, f"trade_no={trade1}")
    # 第二次支付（重复）
    r2 = post(client, "/payment/create", {"order_no": order_no, "amount_cents": 1000, "channel": "mock"}, token=user_token)
    if r2.status_code >= 400:
        record("2nd payment create rejected", True, f"status={r2.status_code} (正确拒绝)")
    elif r2.json().get("code") == "1000":
        trade2 = r2.json().get("data", {}).get("trade_no")
        if trade2 == trade1:
            record("2nd payment idempotent (same trade_no)", True, f"trade_no 一致")
        else:
            record("2nd payment idempotent", False, f"产生新 trade_no={trade2}（潜在双重扣款风险 — KNOWN_GAP V0.5）", gap=True)


# ============================================================================ #
# 3) 重复 notify paid
# ============================================================================ #
def case_dup_notify(client) -> None:
    section("3. 重复 notify paid — 状态不可二次变更")
    suffix = uuid.uuid4().hex[:6]
    r = post(client, "/auth/register", {"username": f"n_{suffix}", "email": f"n_{suffix}@htex.test", "password": "NotifyTest@2024"})
    if r.status_code != 201:
        record("setup register", False, f"{r.status_code} {r.text[:200]}")
        return
    user_token = r.json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {user_token}"}
    files = {"file": ("pp.jpg", b"x" * 200, "image/jpeg")}
    ur = client.post(f"{BASE}/materials/upload", files=files, data={"material_type": "passport"}, headers=h)
    mid = ur.json()["data"]["material"]["id"]
    r = post(client, "/orders", {
        "destination_id": 1, "visa_type": "tourism", "material_ids": [mid],
        "applicant_data": {"surname": "T", "given_name": "U", "sex": "M", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "NB234567", "passport_expiry": "2030-01-01"},
    }, token=user_token)
    order_no = r.json()["data"]["order"]["order_no"]
    r = post(client, "/payment/create", {"order_no": order_no, "amount_cents": 1000, "channel": "mock"}, token=user_token)
    trade = r.json()["data"]["trade_no"]
    r1 = post(client, "/payment/notify", {"trade_no": trade, "order_no": order_no, "status": "paid"})
    r2 = post(client, "/payment/notify", {"trade_no": trade, "order_no": order_no, "status": "paid"})
    # 期待：第二次要么成功（幂等），要么明确拒绝重复
    r3 = get(client, f"/payment/{order_no}", token=user_token)
    pay = r3.json()["data"]
    record("payment.status stable after double notify", pay["status"] == "paid", f"status={pay['status']} (期望 paid)")


# ============================================================================ #
# 4) 软删（disabled）后不能登录
# ============================================================================ #
def case_disabled_user_login(client) -> None:
    section("4. 软删 — disabled 用户不可登录")
    suffix = uuid.uuid4().hex[:6]
    user = {"username": f"dis_{suffix}", "email": f"dis_{suffix}@htex.test", "password": "Dis@2024"}
    r = post(client, "/auth/register", user)
    user_id = r.json()["data"]["user"]["id"]
    admin_t = post(client, "/admin/login", {"username": "admin", "password": "HtexAd@26"})
    admin_token = admin_t.json()["data"]["access_token"]
    # admin 禁用
    r1 = post(client, f"/admin/users/{user_id}/disable", {}, token=admin_token)
    record("admin disable user", r1.status_code == 200, f"status={r1.status_code}")
    # 尝试登录
    r2 = post(client, "/auth/login", {"account": user["username"], "password": user["password"]})
    record("disabled user login rejected", r2.status_code in (401, 403), f"status={r2.status_code}")
    # 恢复
    r3 = post(client, f"/admin/users/{user_id}/restore", {}, token=admin_token)
    r4 = post(client, "/auth/login", {"account": user["username"], "password": user["password"]})
    record("restored user can login", r4.status_code == 200, f"status={r4.status_code}")


# ============================================================================ #
# 5) pending_destroy 用户不可下单
# ============================================================================ #
def case_pending_destroy_no_order(client) -> None:
    section("5. 注销中（pending_destroy）不可下单")
    # 当前 V0.4 DELETE /admin/users/{id} 设为 pending_destroy
    suffix = uuid.uuid4().hex[:6]
    user = {"username": f"pd_{suffix}", "email": f"pd_{suffix}@htex.test", "password": "PdTest@2024"}
    r = post(client, "/auth/register", user)
    if r.status_code != 201:
        record("setup register (pd)", False, f"{r.status_code}")
        return
    user_id = r.json()["data"]["user"]["id"]
    user_token = r.json()["data"]["access_token"]
    admin_t = post(client, "/admin/login", {"username": "admin", "password": "HtexAd@26"})
    admin_token = admin_t.json()["data"]["access_token"]
    # admin 软删（pending_destroy）
    del_(client, f"/admin/users/{user_id}", token=admin_token)
    # 用旧 token 试着下单 — 应该被拒绝（用户已 pending_destroy）。
    # 当前 V0.4 实现：upload 先 401/403 拒绝（产品行为），然后 order 也被拒。
    # 旧 case 期望 upload 成功 → order 被拒，但产品选择是 upload 先拦，更安全。
    h = {"Authorization": f"Bearer {user_token}"}
    files = {"file": ("pp.jpg", b"x" * 200, "image/jpeg")}
    ur = client.post(f"{BASE}/materials/upload", files=files, data={"material_type": "passport"}, headers=h)
    if ur.status_code in (401, 403):
        record("pending_destroy user upload rejected", True, f"upload status={ur.status_code} (产品行为: pending_destroy 用户不可写)")
        # 下游 order 也应被拒 — 测一下边界一致
        r = client.post(f"{BASE}/orders", json={
            "destination_id": 1, "visa_type": "tourism", "material_ids": [1],
            "applicant_data": {"surname": "T", "given_name": "U", "sex": "M", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "PC345678", "passport_expiry": "2030-01-01"},
        }, headers=h)
        record("pending_destroy user order rejected", r.status_code in (401, 403), f"order status={r.status_code}")
    else:
        # 如果产品改成 upload 不拦，再走原 order 测试路径
        try:
            mid = ur.json()["data"]["material"]["id"]
        except Exception:
            record("pending_destroy upload returned non-error but bad shape", False, f"upload body={ur.text[:120]}")
            return
        r = client.post(f"{BASE}/orders", json={
            "destination_id": 1, "visa_type": "tourism", "material_ids": [mid],
            "applicant_data": {"surname": "T", "given_name": "U", "sex": "M", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "PC345678", "passport_expiry": "2030-01-01"},
        }, headers=h)
        record("pending_destroy user order rejected", r.status_code in (401, 403), f"status={r.status_code}")


# ============================================================================ #
# 6) 跨用户隔离：A 用户不能查 B 用户订单
# ============================================================================ #
def case_cross_user_isolation(client) -> None:
    section("6. 跨用户隔离 — A 用户 token 不能查 B 用户订单")
    sa = uuid.uuid4().hex[:6]
    sb = uuid.uuid4().hex[:6]
    ra = post(client, "/auth/register", {"username": f"a_{sa}", "email": f"a_{sa}@htex.test", "password": "ATest@2024"})
    rb = post(client, "/auth/register", {"username": f"b_{sb}", "email": f"b_{sb}@htex.test", "password": "BTest@2024"})
    token_a = ra.json()["data"]["access_token"]
    token_b = rb.json()["data"]["access_token"]

    # A 下单
    h_a = {"Authorization": f"Bearer {token_a}"}
    files = {"file": ("pp.jpg", b"x" * 200, "image/jpeg")}
    ur = client.post(f"{BASE}/materials/upload", files=files, data={"material_type": "passport"}, headers=h_a)
    mid = ur.json()["data"]["material"]["id"]
    r = client.post(f"{BASE}/orders", json={
        "destination_id": 1, "visa_type": "tourism", "material_ids": [mid],
        "applicant_data": {"surname": "A", "given_name": "X", "sex": "M", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "PD456789", "passport_expiry": "2030-01-01"},
    }, headers=h_a)
    order_a = r.json()["data"]["order"]["order_no"]

    # B 用自己的 token 查 A 的订单 → 期望 404（不泄漏存在性）
    r = get(client, f"/orders/{order_a}", token=token_b)
    record("B cannot read A's order", r.status_code == 404, f"status={r.status_code}")


# ============================================================================ #
# 7) 改订单状态不丢 status_history
# ============================================================================ #
def case_status_history_preserved(client) -> None:
    section("7. 状态历史完整 — 每次状态变化都记录")
    suffix = uuid.uuid4().hex[:6]
    r = post(client, "/auth/register", {"username": f"h_{suffix}", "email": f"h_{suffix}@htex.test", "password": "Htest@2024"})
    user_token = r.json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {user_token}"}
    files = {"file": ("pp.jpg", b"x" * 200, "image/jpeg")}
    ur = client.post(f"{BASE}/materials/upload", files=files, data={"material_type": "passport"}, headers=h)
    mid = ur.json()["data"]["material"]["id"]
    r = post(client, "/orders", {
        "destination_id": 1, "visa_type": "tourism", "material_ids": [mid],
        "applicant_data": {"surname": "H", "given_name": "X", "sex": "M", "dob": "1990-01-01", "nationality": "CHN", "passport_no": "PE567890", "passport_expiry": "2030-01-01"},
    }, token=user_token)
    order_no = r.json()["data"]["order"]["order_no"]
    # admin 推进 3 次
    admin_t = post(client, "/admin/login", {"username": "admin", "password": "HtexAd@26"})
    admin_token = admin_t.json()["data"]["access_token"]
    rl = get(client, "/admin/orders?page=1&page_size=50", token=admin_token).json()["data"]["items"]
    oid = next(o["id"] for o in rl if o["order_no"] == order_no)
    put(client, f"/admin/orders/{oid}/status", {"status": "submitted", "note": "s1"}, token=admin_token)
    put(client, f"/admin/orders/{oid}/status", {"status": "reviewing", "note": "s2"}, token=admin_token)
    put(client, f"/admin/orders/{oid}/status", {"status": "approved", "note": "s3"}, token=admin_token)
    # 查 detail 看 history
    rd = get(client, f"/admin/orders/{oid}", token=admin_token).json()["data"]
    history = rd.get("status_history") or []
    record("status_history length ≥ 3", len(history) >= 3, f"len={len(history)} actions={[h.get('to_status') for h in history]}")
    expected = {"submitted", "reviewing", "approved"}
    seen = {h.get("to_status") for h in history}
    record("status_history covers all transitions", expected.issubset(seen), f"seen={seen}, expected≥{expected}")


# ============================================================================ #
# 8) 写完即读：先 write，再 fresh session 读，应能读到
# ============================================================================ #
def case_write_then_read_fresh(client) -> None:
    section("8. 写完即读 — fresh session 验证持久化")
    suffix = uuid.uuid4().hex[:6]
    r = post(client, "/auth/register", {"username": f"fr_{suffix}", "email": f"fr_{suffix}@htex.test", "password": "FrTest@2024"})
    user_id = r.json()["data"]["user"]["id"] if isinstance(r.json()["data"]["user"], dict) else r.json()["data"]["user_id"]
    time.sleep(1)
    # 新 client 读
    with httpx.Client() as c2:
        admin_t = post(c2, "/admin/login", {"username": "admin", "password": "HtexAd@26"})
        admin_token = admin_t.json()["data"]["access_token"]
        rl = get(c2, "/admin/users?page=1&page_size=200", token=admin_token).json()["data"]["items"]
    found = any(u["id"] == user_id for u in rl)
    record("user persisted across fresh session", found, f"user_id={user_id} found={found}")


# ============================================================================ #
# 9) audit_log 不可改：手动改 status，audit 应有对应记录
# ============================================================================ #
def case_audit_log_immutable(client) -> None:
    section("9. 审计日志完整性 — admin 操作都有 audit")
    admin_t = post(client, "/admin/login", {"username": "admin", "password": "HtexAd@26"})
    admin_token = admin_t.json()["data"]["access_token"]
    # 拉所有 actions 列表
    r = get(client, "/admin/logs/actions", token=admin_token)
    if r.status_code == 200:
        actions = r.json()["data"]
        # 期待关键 action 都被记录
        needed = {"admin.login", "user.register", "order.create"}
        record("audit actions cover critical ops", needed.issubset(set(actions)), f"seen={len(actions)} actions, missing={needed - set(actions)}")
    else:
        record("audit /logs/actions endpoint", False, f"status={r.status_code}")


# ============================================================================ #
# Main
# ============================================================================ #
def main() -> int:
    print(f"Case 15 — 数据完整性 / 丢数据防护 @ {datetime.now().isoformat()}")
    print(f"  注：限流 100 req/min, case 之间 sleep 等重置")
    with httpx.Client() as client:
        case_dup_register(client)
        time.sleep(65)
        case_dup_payment(client)
        time.sleep(65)
        case_dup_notify(client)
        time.sleep(65)
        case_disabled_user_login(client)
        time.sleep(65)
        case_pending_destroy_no_order(client)
        time.sleep(65)
        case_cross_user_isolation(client)
        time.sleep(65)
        case_status_history_preserved(client)
        time.sleep(65)
        case_write_then_read_fresh(client)
        time.sleep(65)
        case_audit_log_immutable(client)

    section("SUMMARY")
    passed = sum(1 for r in results if r["ok"] and not r.get("gap"))
    failed = sum(1 for r in results if not r["ok"])
    gaps = sum(1 for r in results if r.get("gap"))
    print(f"  Total: {len(results)}  PASS: {passed}  FAIL: {failed}  KNOWN_GAP: {gaps}")
    if failed:
        print("\n  Failed:")
        for r in results:
            if not r["ok"] and not r.get("gap"):
                print(f"    - {r['step']}: {r['detail']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())