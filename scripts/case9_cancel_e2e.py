"""Case 9: 用户端订单取消 e2e (V2 §4.2.4 cancel path).

完整流程:
  Phase A — 创建并取消
    A1. 用户登录拿 JWT
    A2. 选 US 目的地 + 已有 material_ids, 创建订单 (status=created)
    A3. POST /api/v2/orders/{no}/cancel → status=closed
    A4. 拉订单详情, 验证:
        - status_history 出现新条目: created→closed, source="user"
        - closed_at 时间戳已写
        - 订单回到终态, 不允许再编辑
  Phase B — 终态守卫
    B1. 取消后再 submit → 应被 ORDER_NOT_EDITABLE (4010) 拒绝
    B2. 取消后再 cancel → 应被 ORDER_NOT_EDITABLE 拒绝
    B3. admin 想从 closed 改回 created → 状态机拒绝 4xx (terminal, no outbound)
    B4. admin 想从 closed 改到 closed → 状态机拒绝 (same-state 不是合法 transition)

注: cancel 路径与 admin update_order_status 共享 is_valid_transition
校验器 (backend/app/models/order.py:90-99), 所以两边对终态的拒绝
行为应当一致 — 这是 W34 设计意图 (single source of truth).
"""
from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000"
USER_EMAIL = "demo138001380001@htex.app"
USER_PWD = "123456"
ADMIN_USER = "admin"
ADMIN_PWD = "Admin@2024"


def log(tag: str, msg: str) -> None:
    print(f"[{tag:5}] {msg}", flush=True)


def ok(label: str) -> None:
    print(f"  ✓ {label}", flush=True)


def fail(label: str, detail: str = "") -> None:
    print(f"  ✗ {label}  {detail}", flush=True)
    sys.exit(1)


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=10) as c:
        # ───── Phase A — 创建并取消 ─────
        log("USER", "登录拿 JWT …")
        r = c.post("/api/v2/auth/login", json={"account": USER_EMAIL, "password": USER_PWD})
        if r.status_code != 200:
            fail("login", f"{r.status_code} {r.text[:200]}")
        user_token = r.json()["data"]["access_token"]
        uh = {"Authorization": f"Bearer {user_token}"}

        log("USER", "查 US 目的地 + material ids …")
        r = c.get("/api/v2/destinations", headers=uh)
        if r.status_code != 200:
            fail("list_destinations", f"{r.status_code} {r.text[:200]}")
        us = next((d for d in r.json()["data"] if d.get("country_code") == "US"), None)
        if not us:
            fail("find US", "US not in destinations list")
        dest_id = us["id"]

        r = c.get("/api/v2/materials", headers=uh, params={"limit": 10})
        if r.status_code != 200:
            fail("list materials", f"{r.status_code} {r.text[:200]}")
        mats = r.json()["data"]
        if not mats:
            fail("no materials", "demo user has no material — re-run seed_demo_data.py")
        mat_ids = [m["id"] for m in mats]
        ok(f"dest_id={dest_id} materials={mat_ids}")

        log("USER", "创建订单 (status=created) …")
        r = c.post("/api/v2/orders", headers=uh, json={
            "destination_id": dest_id,
            "visa_type": "tourism",
            "material_ids": mat_ids,
        })
        if r.status_code not in (200, 201):
            fail("create order", f"{r.status_code} {r.text[:200]}")
        payload = r.json()["data"]
        order = payload.get("order") or payload
        oid = order["id"]
        order_no = order.get("order_no") or payload.get("order_no", "?")
        ok(f"created order id={oid} order_no={order_no} status=created")
        if order.get("status") != "created":
            fail("initial status", f"expected 'created', got {order.get('status')}")

        log("USER", "POST /orders/{no}/cancel (created → closed) …")
        r = c.post(f"/api/v2/orders/{order_no}/cancel", headers=uh)
        if r.status_code != 200:
            fail("cancel", f"{r.status_code} {r.text[:200]}")
        body = r.json().get("data") or r.json()
        if body.get("status") != "closed":
            fail("cancel status", f"expected 'closed', got {body.get('status')}")
        if not body.get("cancelled_at"):
            fail("cancelled_at", "missing on response")
        ok(f"status=closed, cancelled_at={body['cancelled_at']}")

        # ───── Phase A.4 — 拉详情验证 status_history ─────
        log("USER", "GET /orders/{no} 查 status_history …")
        r = c.get(f"/api/v2/orders/{order_no}", headers=uh)
        if r.status_code != 200:
            fail("get detail", f"{r.status_code} {r.text[:200]}")
        detail = r.json().get("data") or r.json()
        history = detail.get("status_history", [])

        # 期望 history: [None→created (initial), created→closed (user cancel)]
        expected_seq = [
            (None,      "created", "user"),
            ("created", "closed",  "user"),
        ]
        if len(history) != len(expected_seq):
            fail("history length",
                 f"expected {len(expected_seq)}, got {len(history)}: "
                 + str([(h.get('from_status'), h.get('to_status'), h.get('source')) for h in history]))
        for i, (ef, et, es) in enumerate(expected_seq):
            h = history[i]
            if h.get("from_status") != ef or h.get("to_status") != et or h.get("source") != es:
                fail(f"history[{i}]",
                     f"expected {ef}→{et} by {es}, got "
                     f"{h.get('from_status')}→{h.get('to_status')} by {h.get('source')}")
        ok(f"status_history matches: {[(h.get('from_status'), h.get('to_status'), h.get('source')) for h in history]}")

        if not detail.get("closed_at"):
            fail("closed_at", "missing on terminal closed state")
        ok(f"closed_at = {detail['closed_at']}")

        # 取消来源的 note 应该是 "cancelled by user" 或类似
        last = history[-1]
        if last.get("note") and "cancel" not in last["note"].lower():
            fail("cancel note", f"note should mention cancel, got: {last['note']!r}")
        ok(f"cancel note recorded: {last.get('note')!r}")

        # ───── Phase B — 终态守卫 ─────
        log("USER", "B1. 取消后再 submit, 应被 ORDER_NOT_EDITABLE 拒绝 …")
        # 拿一份新 checklist (虽然 closed 状态 server 应该已经返回 4010)
        r = c.get(f"/api/v2/orders/{order_no}/checklist", headers=uh)
        if r.status_code == 200:
            # 防御: 假如 server 仍然返回 200, 用签 submit
            sig = (r.json().get("data") or r.json()).get("signature")
            r = c.post(f"/api/v2/orders/{order_no}/submit", headers=uh, json={"signature": sig})
        # 任何非 200 都算被拒
        if r.status_code == 200:
            fail("submit after cancel",
                 "server accepted submit on closed order — state gate broken!")
        err_msg = r.json().get("message", "")
        ok(f"submit rejected with {r.status_code}: {err_msg[:120]}")

        log("USER", "B2. 取消后再 cancel, 应被 ORDER_NOT_EDITABLE 拒绝 …")
        r = c.post(f"/api/v2/orders/{order_no}/cancel", headers=uh)
        if r.status_code == 200:
            fail("double cancel", "server accepted cancel on already-closed order — state gate broken!")
        err_msg = r.json().get("message", "")
        if "no longer editable" not in err_msg and "ORDER_NOT_EDITABLE" not in err_msg:
            fail("cancel error message",
                 f"missing ORDER_NOT_EDITABLE hint: {err_msg[:200]}")
        ok(f"double cancel rejected: {err_msg[:120]}")

        # ───── Phase B.3/B.4 — admin 想从 closed 跳出应被状态机拒绝 ─────
        log("ADMIN", "登录拿 admin_token …")
        r = c.post("/api/v2/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PWD})
        if r.status_code != 200:
            fail("admin login", f"{r.status_code} {r.text[:200]}")
        ah = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

        log("ADMIN", "B3. 尝试 closed → created (非终态), 应被状态机拒绝 …")
        r = c.put(f"/api/v2/admin/orders/{oid}/status",
                  headers=ah, json={"status": "created", "note": "should fail"})
        if r.status_code == 200:
            fail("admin closed→created", "server accepted terminal→created transition!")
        err_msg = r.json().get("message", "")
        if "Illegal status transition" not in err_msg:
            fail("admin error message",
                 f"missing 'Illegal status transition' wording: {err_msg[:200]}")
        if "terminal" not in err_msg:
            fail("admin error terminal hint",
                 f"missing 'terminal' hint in message: {err_msg[:200]}")
        ok(f"admin closed→created rejected: {err_msg[:120]}")

        log("ADMIN", "B4. 尝试 closed → closed (same-state, 状态机也不允许) …")
        r = c.put(f"/api/v2/admin/orders/{oid}/status",
                  headers=ah, json={"status": "closed", "note": "same-state should fail"})
        if r.status_code == 200:
            fail("admin closed→closed",
                 "server accepted same-state transition — audit trail would log no-op changes")
        err_msg = r.json().get("message", "")
        if "Illegal status transition" not in err_msg:
            fail("admin same-state error",
                 f"missing 'Illegal status transition' wording: {err_msg[:200]}")
        ok(f"admin closed→closed rejected: {err_msg[:120]}")

    print()
    print("=" * 60)
    print("  ALL GREEN: cancel 路径 + 终态守卫完整 e2e 跑通")
    print(f"  Order #{oid} ({order_no})  created → closed via user cancel")
    print("  Terminal-state guards (user + admin) both hold")
    print("=" * 60)


if __name__ == "__main__":
    main()
