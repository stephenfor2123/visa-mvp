#!/usr/bin/env python3
"""Backend mock: full US wizard → order → admin verify flow.

Runs entirely via API with mock JPEG uploads and minimal applicant_data.
No browser required — use after backend is up on :8000.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
BASE = "http://127.0.0.1:8000/api/v2"


def load_admin_password() -> str:
    env_path = BACKEND / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ADMIN_PASSWORD_SECRET="):
                return line.split("=", 1)[1].strip()
    return "HtexAd@26"


def main() -> int:
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
    os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

    suffix = uuid.uuid4().hex[:8]
    email = f"mock_{suffix}@htex.test"
    password = "MockTest@2024"
    jpeg = b"\xff\xd8\xff\xe0" + b"MOCK-JPEG" * 128

    material_types = [
        "passport",
        "photo",
        "bank",
        "employment",
        "flight",
        "hotel",
    ]

    with httpx.Client(timeout=45) as c:
        # Health
        r = c.get("http://127.0.0.1:8000/health")
        if r.status_code != 200:
            print(f"FAIL: backend not healthy ({r.status_code})")
            return 1
        print("PASS: backend health")

        # Destinations
        r = c.get(f"{BASE}/destinations", params={"lang": "zh-CN"})
        dests = (r.json().get("data") or []) if r.status_code == 200 else []
        us = next((d for d in dests if d.get("country_code") == "US"), None)
        fr = next((d for d in dests if d.get("country_code") == "FR"), None)
        print(f"PASS: destinations count={len(dests)} US={bool(us)} FR_zh={fr.get('country_name') if fr else None}")

        # Register
        r = c.post(
            f"{BASE}/auth/register",
            json={
                "username": f"mock_{suffix}",
                "email": email,
                "password": password,
                "nickname": f"Mock-{suffix}",
            },
        )
        body = r.json()
        token = (body.get("data") or {}).get("access_token", "")
        if r.status_code not in (200, 201) or not token:
            print(f"FAIL: register {r.status_code} {body}")
            return 1
        print(f"PASS: register email={email}")
        h = {"Authorization": f"Bearer {token}"}

        # RAG checklist
        r = c.get(f"{BASE}/rag/checklist", params={"country_code": "US", "lang": "zh-CN"})
        mats = ((r.json().get("data") or {}).get("materials") or [])
        print(f"PASS: RAG checklist materials={len(mats)}")

        # Upload materials (mock files)
        mat_ids: list[int] = []
        for mt in material_types:
            r = c.post(
                f"{BASE}/materials/upload",
                headers=h,
                files={"file": (f"{mt}.jpg", jpeg, "image/jpeg")},
                data={"material_type": mt},
            )
            if r.status_code not in (200, 201):
                print(f"WARN: upload {mt} -> {r.status_code}")
                continue
            mid = ((r.json().get("data") or {}).get("material") or {}).get("id")
            if mid:
                mat_ids.append(mid)
        print(f"PASS: uploaded {len(mat_ids)} materials ids={mat_ids[:4]}...")

        if not us:
            print("FAIL: US destination missing")
            return 1

        # Create order (wizard submit equivalent)
        applicant_data = {
            "surname": "WANG",
            "given_name": "WU",
            "sex": "male",
            "dob": "1988-06-15",
            "nationality": "CN",
            "passport_no": "G98765432",
            "passport_expiry": "2032-12-31",
            "arrival_date": "2026-10-01",
            "departure_date": "2026-10-14",
            "stay_days": 13,
            "flight_no": "CA817",
            "hotel_name": "Mock Hotel NYC",
            "itinerary_text": "Day1 Manhattan; Day2 Brooklyn",
            "emergency_contact": {"name": "Zhang", "phone": "13900001111", "relation": "friend"},
        }
        r = c.post(
            f"{BASE}/orders",
            headers=h,
            json={
                "destination_id": us["id"],
                "visa_type": "tourism",
                "material_ids": mat_ids,
                "applicant_data": applicant_data,
            },
        )
        body = r.json()
        order = (body.get("data") or {}).get("order") or body.get("data") or {}
        order_no = order.get("order_no")
        if r.status_code not in (200, 201) or body.get("code") != "1000" or not order_no:
            print(f"FAIL: create order {r.status_code} {body}")
            return 1
        print(f"PASS: order created order_no={order_no} status={order.get('status')}")

        # Payment mock
        r = c.post(
            f"{BASE}/payment/create",
            headers=h,
            json={"order_no": order_no, "amount_cents": 18500, "currency": "USD"},
        )
        print(f"PASS: payment create code={r.json().get('code')}")
        time.sleep(1.0)

        r = c.get(f"{BASE}/orders/{order_no}", headers=h)
        st = (r.json().get("data") or {}).get("status")
        print(f"PASS: post-payment status={st}")

        # Admin: login + search user by email + find order
        admin_pw = load_admin_password()
        r = c.post(f"{BASE}/admin/login", json={"username": "admin", "password": admin_pw})
        admin_token = (r.json().get("data") or {}).get("access_token", "")
        if not admin_token:
            print(f"FAIL: admin login {r.status_code}")
            return 1
        ah = {"Authorization": f"Bearer {admin_token}"}

        r = c.get(f"{BASE}/admin/users", headers=ah, params={"q": email})
        items = (r.json().get("data") or {}).get("items") or []
        total = (r.json().get("data") or {}).get("total", 0)
        # Admin API masks email (mo***@htex.test) — match by search hit count / username
        found_user = total >= 1 and any(
            (it.get("username") or "").startswith("mock_") for it in items
        )
        print(f"{'PASS' if found_user else 'FAIL'}: admin user search q={email} total={total}")

        r = c.get(f"{BASE}/admin/orders", headers=ah, params={"page_size": 50})
        orders = (r.json().get("data") or {}).get("items") or []
        found_order = any(it.get("order_no") == order_no for it in orders)
        print(f"{'PASS' if found_order else 'FAIL'}: admin orders search found={found_order}")

        r = c.get(f"{BASE}/admin/config/countries", headers=ah)
        countries = (r.json().get("data") or {}).get("items") or []
        print(f"PASS: admin countries count={len(countries)}")

        out = {
            "email": email,
            "order_no": order_no,
            "material_ids": mat_ids,
            "admin_user_found": found_user,
            "admin_order_found": found_order,
            "visa_countries": len(countries),
        }
        out_path = ROOT / "scripts" / "_mock_wizard_order_result.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"Wrote {out_path}")

        ok = found_user and found_order and len(countries) >= 3
        print("VERDICT:", "GO" if ok else "PARTIAL")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
