"""End-to-end smoke test for /api/v2/ds160/* against a running uvicorn.

Assumes:
  - Backend running at http://127.0.0.1:8000
  - A test user exists (created via POST /auth/register before this script)
  - A US destination with id=1 exists
  - A passport material uploaded under that user

Steps:
  1. Login as ds160_e2e@test.local
  2. Upload a fresh passport material
  3. Create an order with full applicant_data
  4. POST /api/v2/ds160/code → expect 200 + code + fingerprint + unchanged=False
  5. POST /api/v2/ds160/code again → expect unchanged=True (idempotent)
  6. POST /api/v2/ds160/code/redeem with the code → expect 200 + profile
  7. Mutate applicant_data (surname change) directly via SQLAlchemy
  8. POST /api/v2/ds160/code/redeem again → expect 409 ARCHIVE_CHANGED (code 11003)
  9. POST /api/v2/ds160/code {force_rotate: true} → get new code
 10. POST /api/v2/ds160/code/redeem with the OLD code → expect 409 CODE_REVOKED (11002)
 11. POST /api/v2/ds160/code/redeem with the NEW code → expect 200 happy

Run with the backend up:
    PYTHONPATH=. .venv/bin/python scripts/_e2e_ds160.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
from sqlalchemy import update

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.order import Order  # noqa: E402

BASE = "http://127.0.0.1:8000/api/v2"
EMAIL = "ds160_e2e@test.local"
PASSWORD = "Test1234"


async def main() -> int:
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        marker = "✅" if ok else "❌"
        print(f"  {marker} {label}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(label + ((' — ' + detail) if detail else ''))

    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as c:
        # ---- 1. Login ----
        r = await c.post("/auth/login", json={"account": EMAIL, "password": PASSWORD})
        check("login", r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print("  aborting — login failed; have you registered this user?")
            return 1
        token = r.json()["data"]["access_token"]
        H = {"Authorization": f"Bearer {token}"}

        # ---- 2. Upload material (1x1 JPEG) ----
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r"
            b"\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.'"
            b' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01'
            b"\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01"
            b"\x01\x00\x00?\x00T\xdb\x9d\x99\xa1\xff\xd9"
        )
        r = await c.post(
            "/materials/upload",
            headers=H,
            data={"material_type": "passport"},
            files={"file": ("p.jpg", jpeg, "image/jpeg")},
        )
        check("upload material", r.status_code == 201, str(r.status_code))
        if r.status_code != 201:
            return 1
        material_id = r.json()["data"]["material"]["id"]

        # ---- 3. Create order ----
        r = await c.post(
            "/orders",
            headers=H,
            json={
                "destination_id": 1,
                "visa_type": "tourism",
                "material_ids": [material_id],
                "applicant_data": {
                    "surname": "NGUYEN",
                    "given_name": "Van An",
                    "passport_no": "B1234567",
                    "nationality": "VN",
                    "birth_date": "1992-05-14",
                },
            },
        )
        check("create order", r.status_code == 201, str(r.status_code))
        if r.status_code != 201:
            return 1
        order_no = r.json()["data"]["order_no"]

        # resolve order.id from order_no
        async with AsyncSessionLocal() as s:
            order = (await s.execute(
                __import__("sqlalchemy").select(Order).where(Order.order_no == order_no)
            )).scalar_one()
            order_id = order.id

        print(f"  order_no={order_no}  order_id={order_id}")

        # ---- 4. First /code call (new code) ----
        r = await c.post("/ds160/code", headers=H, json={"order_id": order_id})
        check("/code first call → 200", r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            return 1
        code1 = r.json()["data"]["code"]
        fp1 = r.json()["data"]["fingerprint"]
        check("/code first unchanged=False", r.json()["data"]["unchanged"] is False)
        check("/code format 12 chars", len(code1) == 12, code1)
        print(f"  code1={code1}  fp1={fp1[:8]}...")

        # ---- 5. Second /code call (idempotent, same archive) ----
        r = await c.post("/ds160/code", headers=H, json={"order_id": order_id})
        check("/code second call → 200", r.status_code == 200)
        check("/code second unchanged=True", r.json()["data"]["unchanged"] is True)
        check("/code second code == first", r.json()["data"]["code"] == code1)

        # ---- 6. /redeem with valid code ----
        r = await c.post("/ds160/code/redeem", json={"code": code1})
        check("/redeem valid → 200", r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            return 1
        profile = r.json()["data"]["profile"]
        check("/redeem profile.identity.surname", profile["identity"]["surname"] == "NGUYEN",
              profile["identity"]["surname"])
        check("/redeem profile.passport.number", profile["passport"]["number"] == "B1234567")

        # ---- 7. Mutate applicant_data ----
        async with AsyncSessionLocal() as s:
            new_data = json.dumps({
                "surname": "TRAN",  # surname change → fingerprint avalanche
                "given_name": "Van An",
                "passport_no": "B1234567",
                "nationality": "VN",
                "birth_date": "1992-05-14",
            })
            await s.execute(update(Order).where(Order.id == order_id).values(applicant_data=new_data))
            await s.commit()

        # ---- 8. /redeem again → 11003 ARCHIVE_CHANGED ----
        r = await c.post("/ds160/code/redeem", json={"code": code1})
        check("/redeem after archive change → 409", r.status_code == 409, str(r.status_code))
        check("/redeem after archive change code=11003",
              r.json().get("code") == "11003", str(r.json().get("code")))

        # ---- 9. force_rotate → new code ----
        r = await c.post("/ds160/code", headers=H,
                         json={"order_id": order_id, "force_rotate": True})
        check("/code force_rotate → 200", r.status_code == 200)
        code2 = r.json()["data"]["code"]
        check("force_rotate new code != old", code2 != code1,
              f"{code1} vs {code2}")
        print(f"  code2={code2}")

        # ---- 10. /redeem with OLD code → 11002 CODE_REVOKED ----
        r = await c.post("/ds160/code/redeem", json={"code": code1})
        check("/redeem with old code → 409", r.status_code == 409)
        check("/redeem with old code code=11002",
              r.json().get("code") == "11002", str(r.json().get("code")))

        # ---- 11. /redeem with NEW code → 200 happy ----
        r = await c.post("/ds160/code/redeem", json={"code": code2})
        check("/redeem with new code → 200", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            check("/redeem new code profile.passport.number",
                  r.json()["data"]["profile"]["passport"]["number"] == "B1234567")

    print()
    if failures:
        print(f"❌ {len(failures)} FAILED:")
        for f in failures:
            print(f"   - {f}")
        return 1
    print("🎉 All 16 e2e checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))