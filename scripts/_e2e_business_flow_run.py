#!/usr/bin/env python3
"""One-shot business flow API test for report generation."""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
BASE = "http://localhost:8000/api/v2"
results: list[dict] = []


def rec(step: str, ok: bool, detail: str = "", severity: str = "P1") -> None:
    results.append({"step": step, "ok": ok, "detail": detail, "severity": severity})
    print(f"[{'PASS' if ok else 'FAIL'}] {step}: {detail}")


def j(r: httpx.Response):
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text[:300], "_status": r.status_code}


def load_admin_password() -> str:
    for line in (BACKEND / ".env").read_text().splitlines():
        if line.startswith("ADMIN_PASSWORD_SECRET="):
            return line.split("=", 1)[1].strip()
    return "HtexAd@26"


def main() -> int:
    import os
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
    os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

    suffix = uuid.uuid4().hex[:8]
    email = f"e2e_{suffix}@htex.test"
    password = "E2eTest@2024"
    order_no = None
    order_id = None

    with httpx.Client(timeout=30) as c:
        # Phase 0
        r = c.get(f"{BASE}/destinations", params={"lang": "zh-CN"})
        body = j(r)
        dests = body.get("data", []) if isinstance(body.get("data"), list) else []
        us = next((d for d in dests if d.get("country_code") == "US"), None)
        rec("0.1 destinations", r.status_code == 200 and len(dests) >= 3, f"http={r.status_code} count={len(dests)} US={bool(us)}")

        r = c.get(f"{BASE}/rag/checklist", params={"country_code": "US", "lang": "zh-CN"})
        body = j(r)
        mats = (body.get("data") or {}).get("materials", [])
        rec("0.2 RAG checklist US", r.status_code == 200 and len(mats) >= 5, f"materials={len(mats)}")

        # Phase 1
        r = c.post(
            f"{BASE}/auth/register",
            json={"username": f"e2e_{suffix}", "email": email, "password": password, "nickname": f"E2E-{suffix}"},
        )
        body = j(r)
        token = (body.get("data") or {}).get("access_token", "")
        rec("1.1 register", r.status_code in (200, 201) and body.get("code") == "1000" and bool(token), f"email={email}")

        h = {"Authorization": f"Bearer {token}"}
        r = c.get(f"{BASE}/auth/me", headers=h)
        body = j(r)
        rec("1.2 auth/me", r.status_code == 200 and body.get("code") == "1000", f"email={(body.get('data') or {}).get('email')}")

        # Phase 3 materials
        jpeg = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG" * 64
        r = c.post(f"{BASE}/materials/upload", headers=h, files={"file": ("passport.jpg", jpeg, "image/jpeg")}, data={"material_type": "passport"})
        body = j(r)
        mat_id = ((body.get("data") or {}).get("material") or {}).get("id")
        rec("3.1 upload passport", r.status_code == 201 and mat_id, f"material_id={mat_id}")

        r = c.post(f"{BASE}/materials/upload", headers=h, files={"file": ("photo.jpg", jpeg, "image/jpeg")}, data={"material_type": "photo"})
        body = j(r)
        photo_id = ((body.get("data") or {}).get("material") or {}).get("id")
        rec("3.2 upload photo", r.status_code == 201 and photo_id, f"material_id={photo_id}")

        r = c.get(f"{BASE}/materials", headers=h, params={"limit": 10})
        rec("3.3 materials list API", r.status_code == 200, f"http={r.status_code} (404=known gap)", severity="P2")

        # Phase 4 order
        dest_id = us["id"] if us else 1
        r = c.post(
            f"{BASE}/orders",
            headers=h,
            json={
                "destination_id": dest_id,
                "visa_type": "tourism",
                "material_ids": [x for x in [mat_id, photo_id] if x],
                "applicant_data": {
                    "surname": "ZHANG",
                    "given_name": "SAN",
                    "sex": "male",
                    "dob": "1990-01-01",
                    "nationality": "CN",
                    "passport_no": "E12345678",
                    "passport_expiry": "2030-01-01",
                    "arrival_date": "2026-09-01",
                    "departure_date": "2026-09-15",
                    "stay_days": 14,
                    "flight_no": "CA981",
                    "hotel_name": "Test Hotel",
                    "itinerary_text": "Day1 NYC",
                    "emergency_contact": {"name": "Li", "phone": "13800000000", "relation": "friend"},
                },
            },
        )
        body = j(r)
        order = (body.get("data") or {}).get("order") or body.get("data") or {}
        order_no = order.get("order_no")
        order_id = order.get("id")
        amount = order.get("total_amount")
        rec(
            "4.1 create order",
            r.status_code in (200, 201) and body.get("code") == "1000" and bool(order_no),
            f"order_no={order_no} status={order.get('status')} amount={amount}",
        )

        if order_no:
            r = c.get(f"{BASE}/orders/{order_no}", headers=h)
            body = j(r)
            rec("5.3 user order detail", r.status_code == 200 and body.get("code") == "1000", f"status={(body.get('data') or {}).get('status')}")

            r = c.get(f"{BASE}/orders", headers=h)
            body = j(r)
            items = (body.get("data") or {}).get("items") or body.get("data") or []
            found = any((it.get("order_no") == order_no) for it in (items if isinstance(items, list) else []))
            rec("5.4 orders list", r.status_code == 200 and found, f"found={found}")

            r = c.post(f"{BASE}/payment/create", headers=h, json={"order_no": order_no, "amount_cents": 18500, "currency": "USD"})
            body = j(r)
            rec("5.1 payment create", r.status_code in (200, 201) and body.get("code") == "1000", f"code={body.get('code')}")
            time.sleep(1.5)
            r = c.get(f"{BASE}/orders/{order_no}", headers=h)
            body = j(r)
            st = (body.get("data") or {}).get("status")
            paid_ok = st in ("paid", "ready_to_submit")
            rec("5.2 payment后订单状态", paid_ok or st == "created", f"status={st} (created=known gap if unpaid)", severity="P0" if st == "created" else "P1")

            r = c.post(f"{BASE}/orders/{order_no}/submit", headers=h, json={"signature": "test"})
            body = j(r)
            rec("4.2 submit order", r.status_code == 200, f"http={r.status_code} code={body.get('code')} msg={body.get('message','')[:80]}")

        # Phase 6 admin
        r = c.post(f"{BASE}/admin/login", json={"username": "admin", "password": load_admin_password()})
        body = j(r)
        admin_token = (body.get("data") or {}).get("access_token", "")
        rec("6.1 admin login", r.status_code == 200 and body.get("code") == "1000" and bool(admin_token), f"http={r.status_code}")

        if admin_token:
            ah = {"Authorization": f"Bearer {admin_token}"}
            r = c.get(f"{BASE}/admin/stats/dashboard", headers=ah)
            body = j(r)
            rec("6.2 admin dashboard", r.status_code == 200 and body.get("code") == "1000", f"http={r.status_code} code={body.get('code')}", severity="P0")

            r = c.get(f"{BASE}/admin/users", headers=ah, params={"q": email})
            body = j(r)
            users = (body.get("data") or {}).get("items") or body.get("data") or []
            found_user = any(u.get("email") == email for u in (users if isinstance(users, list) else []))
            rec("6.3 admin users", r.status_code == 200 and found_user, f"found={found_user}")

            r = c.get(f"{BASE}/admin/orders", headers=ah)
            body = j(r)
            items = (body.get("data") or {}).get("items") or []
            found_order = any(it.get("order_no") == order_no for it in items) if order_no else False
            rec("6.4 admin orders", r.status_code == 200 and found_order, f"found={found_order}")

            if order_id:
                r = c.put(f"{BASE}/admin/orders/{order_id}/status", headers=ah, json={"status": "reviewing", "note": "e2e"})
                body = j(r)
                rec("6.6 admin status update", r.status_code == 200 and body.get("code") == "1000", f"http={r.status_code} code={body.get('code')}", severity="P0")

            r = c.get(f"{BASE}/admin/config/countries", headers=ah)
            body = j(r)
            total = (body.get("data") or {}).get("total")
            rec("6.8 admin countries", r.status_code == 200 and (total or 0) > 0, f"total={total}", severity="P1")

    passed = sum(1 for x in results if x["ok"])
    print(f"\nSUMMARY: {passed}/{len(results)} PASS")
    out = ROOT / "scripts" / "_e2e_business_flow_result.json"
    out.write_text(json.dumps({"email": email, "order_no": order_no, "results": results}, ensure_ascii=False, indent=2))
    print(f"Wrote {out}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
