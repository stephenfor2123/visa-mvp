"""Case 10: scheduler poll-tick 路径 e2e (V2 §4.2.4 + §4.3 RPA handoff).

完整流程:
  Phase A — 准备: 创建 + submit + admin 推进到 reviewing
    A1. 用户登录, 创建订单, submit (status=submitted, source=user)
    A2. admin 登录, 推进到 reviewing (source=admin)
  Phase B — scheduler tick 推进
    B1. X-System-Key 鉴权, POST /scheduler/poll-tick
    B2. 验证 response.data 里 ticked/changed 数字合理
    B3. 持续 tick 直到目标订单走到 approved 或 rejected (source=scheduler)
  Phase C — 验证 status_history 完整链路
    C1. 拉 admin 订单详情, 验证 history 完整序列:
        None→created(user) → created→submitted(user) → submitted→reviewing(admin)
        → reviewing→approved/rejected(scheduler)
    C2. 验证 poll_log 间接落库: history 里 source=scheduler 这一行存在
    C3. 验证 reviewed_at 时间戳已写
  Phase D — 异常分支: admin override 推到 abnormal/failed
    D1. 准备一个新订单, admin 推到 reviewing
    D2. admin override 推到 abnormal (合法转换 reviewing→abnormal)
    D3. admin override 推到 failed (新建一个走 reviewing→failed)
    D4. 验证 history 出现 source=admin, terminal 状态 closed_at 已写

注:
  * stub 规则 (backend/app/services/poll_service.py:89):
    - submitted: 50%→reviewing, 10%→rejected, 40% stay
    - reviewing: 30%→approved, 10%→rejected, 60% stay
  * 每次 tick 用 fresh random.Random(), 所以多次 tick 累加命中率
  * Phase D 的 abnormal/failed 是 admin 端走的 (状态机允许 reviewing→abnormal
    和 reviewing→failed), 因为 stub 不产这些状态
  * rpa_callback 路径 (source=rpa) 当前没有 HTTP 端点 — service 层
    PollService.record_change() 支持, 但需要直连 DB 调用, 留待 W3 webhook
    上线后补充
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
USER_EMAIL = "demo138001380001@htex.app"
USER_PWD = "Htex@2026"
ADMIN_USER = "admin"
ADMIN_PWD = "HtexAd@26"
SYSTEM_KEY = "dev-system-key-change-me-in-prod-visa-mvp-2026"

# Poll-tick 重试上限: 经验上 10 次内 reviewing→approved/rejected 命中率 99%
MAX_TICKS = 10
TICK_INTERVAL_S = 0.2


def log(tag: str, msg: str) -> None:
    print(f"[{tag:5}] {msg}", flush=True)


def ok(label: str) -> None:
    print(f"  ✓ {label}", flush=True)


def fail(label: str, detail: str = "") -> None:
    print(f"  ✗ {label}  {detail}", flush=True)
    sys.exit(1)


def login_user(c: httpx.Client) -> dict[str, str]:
    r = c.post("/api/v2/auth/login", json={"account": USER_EMAIL, "password": USER_PWD})
    if r.status_code != 200:
        fail("user login", f"{r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def login_admin(c: httpx.Client) -> dict[str, str]:
    r = c.post("/api/v2/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PWD})
    if r.status_code != 200:
        fail("admin login", f"{r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def create_and_submit(c: httpx.Client, uh: dict[str, str]) -> tuple[int, str]:
    """Create a fresh US order + submit it. Returns (oid, order_no)."""
    r = c.get("/api/v2/destinations", headers=uh)
    us = next((d for d in r.json()["data"] if d.get("country_code") == "US"), None)
    if not us:
        fail("find US", "US not in destinations list")
    r = c.get("/api/v2/materials", headers=uh, params={"limit": 10})
    mat_ids = [m["id"] for m in r.json()["data"]]
    if not mat_ids:
        fail("no materials", "demo user has no material — re-run seed_demo_data.py")

    r = c.post("/api/v2/orders", headers=uh, json={
        "destination_id": us["id"],
        "visa_type": "tourism",
        "material_ids": mat_ids,
    })
    if r.status_code not in (200, 201):
        fail("create order", f"{r.status_code} {r.text[:200]}")
    payload = r.json()["data"]
    order = payload.get("order") or payload
    oid = order["id"]
    order_no = order.get("order_no") or payload.get("order_no", "?")

    r = c.get(f"/api/v2/orders/{order_no}/checklist", headers=uh)
    sig = (r.json().get("data") or r.json()).get("signature")
    r = c.post(f"/api/v2/orders/{order_no}/submit", headers=uh, json={"signature": sig})
    if r.status_code != 200:
        fail("submit", f"{r.status_code} {r.text[:200]}")
    return oid, order_no


def admin_transition(
    c: httpx.Client, ah: dict[str, str], oid: int, new_status: str
) -> None:
    r = c.put(
        f"/api/v2/admin/orders/{oid}/status",
        headers=ah,
        json={"status": new_status, "note": f"e2e phase10 → {new_status}"},
    )
    if r.status_code != 200:
        fail(f"admin {new_status}", f"{r.status_code} {r.text[:200]}")


def fetch_history(c: httpx.Client, ah: dict[str, str], oid: int) -> list[dict]:
    r = c.get(f"/api/v2/admin/orders/{oid}", headers=ah)
    if r.status_code != 200:
        fail("get order detail", f"{r.status_code} {r.text[:200]}")
    return (r.json().get("data") or r.json()).get("status_history", [])


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=10) as c:
        uh = login_user(c)
        ah = login_admin(c)
        ok("user + admin tokens ready")

        # ───── Phase A — 创建 + submit + admin 推到 reviewing ─────
        log("PHASE-A", "创建订单 + submit + admin 推到 reviewing …")
        oid_a, order_no_a = create_and_submit(c, uh)
        ok(f"order #{oid_a} ({order_no_a}) status=submitted (source=user)")
        admin_transition(c, ah, oid_a, "reviewing")
        ok(f"admin override → reviewing (source=admin)")

        # ───── Phase B — scheduler tick 推到终态 ─────
        log("PHASE-B", f"开始 tick, 最多 {MAX_TICKS} 次 …")
        terminal_status = None
        total_ticked = 0
        total_changed = 0
        for tick_i in range(1, MAX_TICKS + 1):
            r = c.post(
                "/scheduler/poll-tick",
                headers={"X-System-Key": SYSTEM_KEY},
            )
            if r.status_code != 200:
                fail(f"poll-tick #{tick_i}", f"{r.status_code} {r.text[:200]}")
            data = r.json().get("data") or r.json()
            ticked = data.get("ticked", 0)
            changed = data.get("changed", 0)
            logs = data.get("logs", [])
            total_ticked += ticked
            total_changed += changed
            log("  TICK", f"#{tick_i} ticked={ticked} changed={changed} logs={len(logs)}")
            for entry in logs:
                if entry.get("order_no") == order_no_a:
                    terminal_status = entry.get("status_after")
                    log("  TICK",
                        f"  → {order_no_a}: {entry.get('status_before')} → "
                        f"{terminal_status} (src={entry.get('poll_source')})")
            if terminal_status:
                break
            time.sleep(TICK_INTERVAL_S)

        if not terminal_status:
            fail("scheduler tick",
                 f"after {MAX_TICKS} ticks order {order_no_a} still not at terminal "
                 f"(stub probability issue?)")
        if terminal_status not in ("approved", "rejected"):
            fail("scheduler tick terminal",
                 f"expected approved/rejected, got {terminal_status}")
        ok(f"scheduler tick pushed order to terminal: {terminal_status} "
           f"(ticked={total_ticked} changed={total_changed})")

        # ───── Phase C — 验证 status_history 完整链路 ─────
        log("PHASE-C", "拉订单详情验证 status_history …")
        history = fetch_history(c, ah, oid_a)
        expected_seq = [
            (None,        "created",   "user"),
            ("created",   "submitted", "user"),
            ("submitted", "reviewing", "admin"),
            ("reviewing", terminal_status, "scheduler"),
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
        ok(f"status_history covers user→admin→scheduler 全链路 ({len(history)} entries)")

        # 验证 reviewed_at 时间戳 (reviewing/approved/rejected 都会写)
        r = c.get(f"/api/v2/admin/orders/{oid_a}", headers=ah)
        detail = r.json().get("data") or r.json()
        if not detail.get("reviewed_at"):
            fail("reviewed_at", "missing on reviewing/approved/rejected state")
        ok(f"reviewed_at = {detail['reviewed_at']}")

        # ───── Phase D — 异常分支: reviewing → abnormal / failed ─────
        log("PHASE-D", "测异常状态 abnormal / failed (admin override) …")

        # D.1 — abnormal
        oid_d1, order_no_d1 = create_and_submit(c, uh)
        admin_transition(c, ah, oid_d1, "reviewing")
        admin_transition(c, ah, oid_d1, "abnormal")
        history = fetch_history(c, ah, oid_d1)
        log("  ABNORMAL", f"order #{oid_d1} history sources: "
             f"{[h.get('source') for h in history]}")
        if not any(h.get("to_status") == "abnormal" and h.get("source") == "admin"
                   for h in history):
            fail("abnormal history",
                 "missing reviewing→abnormal entry by admin source")
        # 异常状态也是终态, 应该写 closed_at
        r = c.get(f"/api/v2/admin/orders/{oid_d1}", headers=ah)
        detail = r.json().get("data") or r.json()
        if not detail.get("closed_at"):
            fail("abnormal closed_at",
                 "abnormal should stamp closed_at (terminal state)")
        ok(f"order #{oid_d1} → abnormal (admin), closed_at={detail['closed_at']}")

        # D.2 — failed
        oid_d2, order_no_d2 = create_and_submit(c, uh)
        admin_transition(c, ah, oid_d2, "reviewing")
        admin_transition(c, ah, oid_d2, "failed")
        history = fetch_history(c, ah, oid_d2)
        if not any(h.get("to_status") == "failed" and h.get("source") == "admin"
                   for h in history):
            fail("failed history",
                 "missing reviewing→failed entry by admin source")
        r = c.get(f"/api/v2/admin/orders/{oid_d2}", headers=ah)
        detail = r.json().get("data") or r.json()
        if not detail.get("closed_at"):
            fail("failed closed_at",
                 "failed should stamp closed_at (terminal state)")
        ok(f"order #{oid_d2} → failed (admin), closed_at={detail['closed_at']}")

        # D.3 — 终态守卫: abnormal 不能再被改
        log("  GUARD", "abnormal → submitted 应被状态机拒绝 (terminal) …")
        r = c.put(f"/api/v2/admin/orders/{oid_d1}/status",
                  headers=ah, json={"status": "submitted", "note": "should fail"})
        if r.status_code == 200:
            fail("abnormal→submitted",
                 "server accepted transition from terminal abnormal!")
        err_msg = r.json().get("message", "")
        if "terminal" not in err_msg:
            fail("abnormal error", f"missing 'terminal' hint: {err_msg[:200]}")
        ok(f"abnormal → submitted rejected: {err_msg[:100]}")

    print()
    print("=" * 60)
    print("  ALL GREEN: scheduler_tick + 异常分支完整 e2e 跑通")
    print(f"  Order #{oid_a} ({order_no_a})  user→admin→scheduler → {terminal_status}")
    print(f"  Order #{oid_d1} (abnormal)  +  Order #{oid_d2} (failed) — terminal guards hold")
    print(f"  Total poll-ticks: {total_ticked} inspected, {total_changed} changed")
    print("=" * 60)


if __name__ == "__main__":
    main()
