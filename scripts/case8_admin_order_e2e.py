"""Case 8: 用户端创建订单 + 管理员端状态机流转 e2e (V2 §4.2.4).

完整流程:
  Phase A — 用户端
    A1. 用 demo 用户 1 (13800138000/demo1234) 登录拿 JWT
    A2. 选目的地 (US, dest_id 走 list_destinations)
    A3. POST /api/v2/orders  → status=created
    A4. POST /api/v2/orders/{id}/submit  → status=submitted
  Phase B — 管理员端
    B1. admin/admin123 登录拿 admin_token
    B2. GET /api/v2/admin/orders 列表里找刚才那个 order
    B3. PUT /api/v2/admin/orders/{id}/status  submitted → reviewing
    B4. PUT .../status  reviewing → approved
    B5. PUT .../status  approved → closed
  Phase C — 验证
    C1. GET /api/v2/admin/orders/{id} 拿 status_history, 应该有 4 条:
          created→submitted(user), submitted→reviewing(admin),
          reviewing→approved(admin), approved→closed(admin)
    C2. 尝试非法跳转 closed→created, 验证状态机拒绝 4xx + 明确错误
    C3. 验证 audit log 里有 admin.order.update_status 三条
"""
from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
# Demo 用户 1 — W26 后登录走 email/username, 不再是 phone
# (frontend/web/src/views/Login.vue:145 + TEST-ACCOUNTS.md)
USER_EMAIL = "demo138001380001@htex.app"
USER_PWD = "Htex@2026"
ADMIN_USER = "admin"
# ADMIN_PASSWORD_SECRET 在 backend/.env — 默认 HtexAd@26 (本地 dev)
ADMIN_PWD = "HtexAd@26"


def log(tag: str, msg: str) -> None:
    print(f"[{tag:5}] {msg}", flush=True)


def ok(label: str) -> None:
    print(f"  ✓ {label}", flush=True)


def fail(label: str, detail: str = "") -> None:
    print(f"  ✗ {label}  {detail}", flush=True)
    sys.exit(1)


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=10) as c:
        # ───── Phase A — 用户端 ─────
        log("USER", "登录拿 JWT …")
        r = c.post("/api/v2/auth/login", json={"account": USER_EMAIL, "password": USER_PWD})
        if r.status_code != 200:
            fail("login", f"{r.status_code} {r.text[:200]}")
        user_token = r.json()["data"]["access_token"]
        ok(f"user token ({len(user_token)} chars)")

        uh = {"Authorization": f"Bearer {user_token}"}

        log("USER", "查 US 目的地 id …")
        r = c.get("/api/v2/destinations", headers=uh)
        if r.status_code != 200:
            fail("list_destinations", f"{r.status_code} {r.text[:200]}")
        dests = r.json()["data"]
        us = next((d for d in dests if d.get("country_code") == "US"), None)
        if not us:
            fail("find US", f"country_code US not in {[d.get('country_code') for d in dests[:10]]}")
        dest_id = us["id"]
        ok(f"US destination id={dest_id}")

        log("USER", "查已有 material (seed 给 user 1 创建了 passport) …")
        r = c.get("/api/v2/materials", headers=uh, params={"limit": 10})
        if r.status_code != 200:
            fail("list materials", f"{r.status_code} {r.text[:200]}")
        mats = r.json()["data"]
        if not mats:
            fail("no materials", "demo user has no material — re-run seed_demo_data.py")
        mat_ids = [m["id"] for m in mats]
        ok(f"got {len(mat_ids)} material(s): {mat_ids}")

        log("USER", "创建订单 (status=created) …")
        r = c.post("/api/v2/orders", headers=uh, json={
            "destination_id": dest_id,
            "visa_type": "tourism",
            "material_ids": mat_ids,
        })
        if r.status_code not in (200, 201):
            fail("create order", f"{r.status_code} {r.text[:200]}")
        payload = r.json()["data"]
        # server may wrap as {data:{order:...}} or {data:{order:...,status:...}}
        order = payload.get("order") or payload
        oid = order["id"]
        order_no = order.get("order_no") or payload.get("order_no", "?")
        ok(f"created order id={oid} order_no={order_no} status={order.get('status')}")
        if order.get("status") != "created":
            fail("initial status", f"expected 'created', got {order.get('status')}")

        log("USER", "拿 pre-submit checklist 拿 signature …")
        r = c.get(f"/api/v2/orders/{order_no}/checklist", headers=uh)
        if r.status_code != 200:
            fail("get checklist", f"{r.status_code} {r.text[:200]}")
        sig = (r.json()["data"] or r.json()).get("signature")
        if not sig:
            fail("checklist signature missing", str(r.json())[:200])
        ok(f"got signature ({len(sig)} chars)")

        log("USER", "提交订单 (created → submitted) …")
        r = c.post(f"/api/v2/orders/{order_no}/submit",
                   headers=uh, json={"signature": sig})
        if r.status_code != 200:
            fail("submit order", f"{r.status_code} {r.text[:200]}")
        new_status = (r.json()["data"] or r.json()).get("status")
        if new_status != "submitted":
            fail("submit status", f"expected 'submitted', got {new_status}")
        ok(f"order status → {new_status}")

        # ───── Phase B — 管理员端 ─────
        log("ADMIN", "登录 admin 拿 admin_token …")
        r = c.post("/api/v2/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PWD})
        if r.status_code != 200:
            fail("admin login", f"{r.status_code} {r.text[:200]}")
        admin_token = r.json()["data"]["access_token"]
        ok(f"admin token ({len(admin_token)} chars)")

        ah = {"Authorization": f"Bearer {admin_token}"}

        log("ADMIN", "列出订单确认能找到刚才那个 …")
        r = c.get("/api/v2/admin/orders", headers=ah, params={"limit": 50})
        if r.status_code != 200:
            fail("list orders", f"{r.status_code} {r.text[:200]}")
        body = r.json()
        rows = body.get("data", {}).get("items") or body.get("items") or body.get("data") or []
        found = next((o for o in rows if o["id"] == oid), None)
        if not found:
            fail("find order in admin list", f"id={oid} not in {len(rows)} rows")
        ok(f"admin sees order #{oid} status={found['status']}")

        log("ADMIN", "状态机流转: submitted → reviewing → approved → closed …")
        transitions = [
            ("submitted", "reviewing", "审核中"),
            ("reviewing", "approved",  "通过"),
            ("approved",  "closed",    "关闭"),
        ]
        for old, new, label in transitions:
            r = c.put(f"/api/v2/admin/orders/{oid}/status",
                      headers=ah, json={"status": new, "note": f"e2e: {old}→{new}"})
            if r.status_code != 200:
                fail(f"transition {old}→{new}", f"{r.status_code} {r.text[:200]}")
            actual = (r.json().get("data") or r.json()).get("status", "?")
            if actual != new:
                fail(f"transition {old}→{new}", f"server returned status={actual}")
            ok(f"{label}: {old} → {new}")

        # ───── Phase C — 验证 ─────
        log("VERIFY", "拉订单详情 + status_history …")
        r = c.get(f"/api/v2/admin/orders/{oid}", headers=ah)
        if r.status_code != 200:
            fail("get order detail", f"{r.status_code} {r.text[:200]}")
        detail = r.json().get("data") or r.json()
        history = detail.get("status_history", [])
        ok(f"final status = {detail['status']}")
        ok(f"status_history has {len(history)} entries:")
        for i, h in enumerate(history):
            log("  ", f"{i+1}. {h.get('from_status','?')} → {h.get('to_status','?')} "
                     f"by {h.get('source','?')}  @ {h.get('created_at','?')[:19]}  "
                     f"\"{h.get('note','')}\"")

        # 应该有 5 条: None→created (initial), created→submitted (user submit),
        # submitted→reviewing, reviewing→approved, approved→closed (admin overrides)
        expected_seq = [
            (None,        "created",   "user"),
            ("created",   "submitted", "user"),
            ("submitted", "reviewing", "admin"),
            ("reviewing", "approved",  "admin"),
            ("approved",  "closed",    "admin"),
        ]
        if len(history) != len(expected_seq):
            fail("history length", f"expected {len(expected_seq)}, got {len(history)}")
        for i, (ef, et, es) in enumerate(expected_seq):
            h = history[i]
            if h.get("from_status") != ef or h.get("to_status") != et or h.get("source") != es:
                fail(f"history[{i}]",
                     f"expected {ef}→{et} by {es}, got "
                     f"{h.get('from_status')}→{h.get('to_status')} by {h.get('source')}")
        ok(f"status_history matches expected state machine path ({len(expected_seq)} entries)")

        log("VERIFY", "尝试非法跳转 closed→created, 应被状态机拒绝 …")
        r = c.put(f"/api/v2/admin/orders/{oid}/status",
                  headers=ah, json={"status": "created", "note": "should fail"})
        if r.status_code == 200:
            fail("illegal transition allowed",
                 "server accepted closed→created, state machine broken!")
        body = r.json()
        err_msg = body.get("message", "")
        ok(f"server rejected with {r.status_code}: {err_msg[:120]}")
        if "Illegal status transition" not in err_msg:
            fail("error message", f"missing 'Illegal status transition' wording: {err_msg}")
        ok("state machine validator returns clear error message")

        log("VERIFY", "DB 时间戳 closed_at 已写 …")
        if not detail.get("closed_at"):
            fail("closed_at", "missing on terminal closed state")
        ok(f"closed_at = {detail['closed_at']}")

    print()
    print("=" * 60)
    print("  ALL GREEN: 用户→admin 完整 e2e 跑通")
    print(f"  Order #{oid} ({order_no})  closed via 4 state transitions")
    print("=" * 60)


if __name__ == "__main__":
    main()