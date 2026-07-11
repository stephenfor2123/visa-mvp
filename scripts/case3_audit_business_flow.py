"""Case 3: Audit 合规审计真业务流."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "HtexAd@26"


def log(tag, msg):
    print(f"[{tag}] {msg}", flush=True)


def user_register_login(client, phone):
    r = client.post("/api/v2/auth/send-code", json={"phone": phone, "phone_country": "+86", "purpose": "register"})
    r.raise_for_status()
    code = r.json()["data"]["code"]
    client.post("/api/v2/auth/register", json={"phone": phone, "phone_country": "+86", "password": "Test1234", "sms_code": code, "language_pref": "zh-CN"}).raise_for_status()
    r = client.post("/api/v2/auth/login", json={"phone": phone, "phone_country": "+86", "password": "Test1234"})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def admin_login(client):
    r = client.post("/api/v2/admin/login", json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
    if r.status_code >= 400:
        raise RuntimeError(f"admin login failed: HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["data"]["access_token"]


def fetch_audit_logs(client, admin_token, action=None, limit=20):
    headers = {"Authorization": f"Bearer {admin_token}"}
    params = {"limit": limit}
    if action:
        params["action"] = action
    r = client.get("/api/v2/admin/logs", params=params, headers=headers)
    r.raise_for_status()
    body = r.json()
    data = body.get("data", {})
    if isinstance(data, list):
        items = data
    else:
        items = data.get("items") or data.get("logs") or []
    return items if isinstance(items, list) else []


def main():
    phone = "139" + str(int(time.time()))[-8:]
    log("START", f"phone={phone}")

    with httpx.Client(base_url=BASE, timeout=30) as client:
        admin_token = admin_login(client)
        log("ADMIN", "admin token OK")

        user_token = user_register_login(client, phone)
        log("USER", f"user token OK")

        log("TRIG", "triggering 5 audit actions...")
        # 1. OCR
        log("TRIG", "[1] ocr.recognize")
        with open(FIXTURE_DIR / "sample_us_passport.jpg", "rb") as f:
            r = client.post("/api/v2/ocr/recognize",
                files={"file": ("us.jpg", f, "image/jpeg")},
                data={"lang": "en"},
                headers={"Authorization": f"Bearer {user_token}"},
                timeout=60,
            )
        log("TRIG", f"  ocr HTTP {r.status_code}")

        # 2. Voice
        log("TRIG", "[2] voice.recognize")
        voice_dir = FIXTURE_DIR / "voice"
        with open(voice_dir / "med_zh.wav", "rb") as f:
            r = client.post("/api/v2/voice/recognize",
                files={"file": ("zh.wav", f, "audio/wav")},
                data={"lang": "zh-CN"},
                headers={"Authorization": f"Bearer {user_token}"},
                timeout=30,
            )
        log("TRIG", f"  voice HTTP {r.status_code}")

        # 3. Material upload (material_type = passport)
        log("TRIG", "[3] materials.upload")
        with open(FIXTURE_DIR / "sample_us_passport.jpg", "rb") as f:
            r = client.post("/api/v2/materials/upload",
                files={"file": ("us.jpg", f, "image/jpeg")},
                data={"material_type": "passport"},
                headers={"Authorization": f"Bearer {user_token}"},
                timeout=30,
            )
        material_id = None
        if r.status_code != 201:
            log("TRIG", f"  upload HTTP {r.status_code}: {r.text[:200]}")
        else:
            material_id = r.json()["data"]["material"]["id"]
            log("TRIG", f"  upload HTTP 201, mat_id={material_id}")

        # 4. Order create
        log("TRIG", "[4] order.create")
        order_id = None
        order_no = None
        if material_id:
            r = client.post("/api/v2/orders",
                json={
                    "destination_id": 1,
                    "visa_type": "tourism",
                    "material_ids": [str(material_id)],
                    "applicant_data": {
                        "surname": "WANG", "given_name": "FIVE", "sex": "M",
                        "dob": "1990-05-05", "nationality": "CN",
                        "passport_no": "EAUDIT789", "passport_expiry": "2031-05-15",
                        "arrival_date": "2026-09-01", "departure_date": "2026-09-15",
                        "stay_days": 14,
                        "emergency_contact": {"name": "AUDIT CONTACT", "phone": "13911112222", "relation": "spouse"},
                    },
                },
                headers={"Authorization": f"Bearer {user_token}"},
            )
            log("TRIG", f"  order HTTP {r.status_code}")
            if r.status_code == 201:
                od = r.json()["data"]
                # CreateOrderResponse 包着 order 字段
                order_obj = od.get("order", od)
                order_id = order_obj.get("id")
                order_no = order_obj.get("order_no")
                log("TRIG", f"  order_id={order_id}, order_no={order_no}")
            else:
                log("TRIG", f"  body: {r.text[:200]}")
        else:
            log("TRIG", "  skipped (no material_id)")

        # 5. Order status change (admin) — PUT /admin/orders/{order_id}/status
        if order_id:
            log("TRIG", "[5] admin.order.update_status")
            r = client.put(f"/api/v2/admin/orders/{order_id}/status",
                json={"status": "submitted", "note": "audit case 3"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            log("TRIG", f"  status_change HTTP {r.status_code}: {r.text[:200]}")
        else:
            log("TRIG", "[5] skipped")

        log("AUDIT", "=" * 50)
        log("AUDIT", "fetching audit logs (admin)...")
        all_actions = ["ocr.recognize", "voice.recognize", "material.upload", "order.create", "admin.order.update_status"]
        summary = {}
        pii_safe = True
        for action in all_actions:
            entries = fetch_audit_logs(client, admin_token, action=action, limit=5)
            summary[action] = len(entries)
            log("AUDIT", f"{action}: {len(entries)} entries")
            if not entries:
                continue
            sample = entries[0]
            payload = sample.get("payload", {})
            if isinstance(payload, str):
                try: payload = json.loads(payload)
                except: pass
            if action == "ocr.recognize":
                ef = payload.get("extracted_fields", {})
                pn = ef.get("passport_no")
                log("AUDIT", f"  payload keys: {list(payload.keys())}")
                log("AUDIT", f"  extracted_fields.passport_no = {pn!r} (PII check)")
                if isinstance(pn, str) and len(pn) > 3 and pn.startswith("E"):
                    pii_safe = False
                    log("AUDIT", f"  ❌ PII 可能泄露")
            elif action == "order.create":
                log("AUDIT", f"  payload: {json.dumps(payload, ensure_ascii=False)[:300]}")

        log("DONE", "=" * 50)
        triggered = sum(1 for v in summary.values() if v > 0)
        log("DONE", f"Audit 真业务流: {triggered}/5 action 有 audit log 记录")
        log("DONE", f"PII 安全: {'✅' if pii_safe else '❌'}")
        return 0 if triggered >= 4 and pii_safe else 1


if __name__ == "__main__":
    sys.exit(main())
