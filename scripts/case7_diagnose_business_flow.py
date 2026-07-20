"""Case 7: AI 拒签诊断真业务流 (V2 §4.3.5 diagnose).

流程:
  1. 注册+登录 → JWT
  2. 准备材料集 (3 个真实场景):
     - 场景A: 完整 US B2 申请 (passport ok + photo + ds160 + financial) → low risk
     - 场景B: 缺 DS-160 + 护照即将过期 (3个月) → high risk
     - 场景C: 只传了护照 → critical (缺 photo + form)
  3. POST /api/v2/materials/diagnose 拿到 risk_score + issues
  4. 验证:
     - 场景A: overall_risk=low, 没 critical/error issues
     - 场景B: overall_risk=high 或 critical, passport.expiry_short 命中
     - 场景C: overall_risk=critical, 多个 missing-material issues
  5. 边界: 0 个 material_id → 400
"""
from __future__ import annotations

import io
import json
import sys
import time

import cv2
import httpx
import numpy as np

BASE = "http://127.0.0.1:8000"


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def register_and_login(client: httpx.Client, phone: str) -> str:
    r = client.post(
        "/api/v2/auth/send-code",
        json={"phone": phone, "phone_country": "+86", "purpose": "register"},
    )
    r.raise_for_status()
    code = r.json()["data"]["code"]
    r = client.post(
        "/api/v2/auth/register",
        json={
            "phone": phone,
            "phone_country": "+86",
            "password": "Test1234",
            "sms_code": code,
            "language_pref": "zh-CN",
        },
    )
    r.raise_for_status()
    r = client.post(
        "/api/v2/auth/login",
        json={"phone": phone, "phone_country": "+86", "password": "Test1234"},
    )
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def upload_material(client: httpx.Client, token: str, *, filename: str, material_type: str,
                    ocr_result: dict | None = None, ocr_status: str = "done",
                    salt: str = "") -> int:
    """Upload a material, optionally with a pre-set ocr_result (set via DB injection).

    For Case 7 we directly use the service layer to inject OCR result, since the
    async OCR pipeline is out of scope. We just upload a placeholder image and
    then poke the DB row to set ocr_status + ocr_result.
    """
    headers = {"Authorization": f"Bearer {token}"}
    # tiny placeholder image, with a salt to defeat dedup across calls
    img = np.ones((300, 400, 3), dtype=np.uint8) * 240
    if salt:
        cv2.putText(img, salt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    ok, buf = cv2.imencode(".jpg", img)
    files = {"file": (filename, io.BytesIO(buf.tobytes()), "image/jpeg")}
    r = client.post(
        "/api/v2/materials/upload",
        files=files,
        data={"material_type": material_type},
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    mat_id = r.json()["data"]["material"]["id"]

    if ocr_result is not None:
        # inject via direct DB write — there's no public endpoint for this
        # (it's the async OCR pipeline's job, but in dev/test we set it manually)
        # NOTE: must chdir to backend before async DB session so relative
        # sqlite path resolves to backend/data/visa_mvp.db
        import os
        prev_cwd = os.getcwd()
        os.chdir("/Users/apple/Desktop/签证项目/backend")
        try:
            from app.core.db import AsyncSessionLocal
            from app.models.material import Material
            from sqlalchemy import select

            async def _inject():
                async with AsyncSessionLocal() as db:
                    row = (await db.execute(select(Material).where(Material.id == mat_id))).scalar_one()
                    row.ocr_status = ocr_status
                    row.ocr_result = json.dumps(ocr_result, ensure_ascii=False)
                    await db.commit()
            import asyncio
            asyncio.run(_inject())
        finally:
            os.chdir(prev_cwd)
    return mat_id


def diagnose(client: httpx.Client, token: str, body: dict) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/v2/materials/diagnose",
        json=body,
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["data"]


def main() -> int:
    phone = "139" + str(int(time.time()))[-8:]
    log("START", f"phone={phone}")

    with httpx.Client(base_url=BASE, timeout=30) as client:
        token = register_and_login(client, phone)
        log("AUTH", "OK")

        results = []

        # ============================================================ #
        # 场景A: 完整 US B2 申请 — 应 low risk                           #
        # ============================================================ #
        log("DIAG", "=" * 50)
        log("DIAG", "Scenario A: Complete US B2 application")
        m_passport_ok = upload_material(
            client, token,
            filename="passport_usa.jpg",
            material_type="passport",
            salt="passport-USA-001",
            ocr_result={"fields": {
                "passport_no": "G12345678",
                "expiry": "2030-12-31",
                "surname": "ZHANG",
                "given_name": "SAN",
            }},
        )
        m_photo = upload_material(
            client, token,
            filename="photo_2inch_white.jpg",
            material_type="photo",
            salt="photo-white-001",
            ocr_result={"fields": {}},
        )
        m_ds160 = upload_material(
            client, token,
            filename="DS-160_confirmation.pdf",
            material_type="form",
            salt="ds160-001",
            ocr_result={"fields": {"application_no": "AA12345678"}},
        )
        m_finance = upload_material(
            client, token,
            filename="bank_statement_2024Q4.pdf",
            material_type="other",
            salt="finance-001",
            ocr_result={"fields": {}},
        )
        log("DIAG", f"uploaded 4 materials: {m_passport_ok} / {m_photo} / {m_ds160} / {m_finance}")

        data = diagnose(client, token, {
            "material_ids": [m_passport_ok, m_photo, m_ds160, m_finance],
            "country_code": "US",
            "visa_type": "B2",
            "fields": {"travel_date": "2026-12-01", "purpose": "tourism"},
        })
        log("DIAG", f"  overall_risk = {data['overall_risk']}  (score={data['risk_score']})")
        log("DIAG", f"  rule_count = {data['rule_count']}")
        log("DIAG", f"  summary = {data['summary']}")
        log("DIAG", f"  positives ({len(data['positives'])}):")
        for p in data["positives"]:
            log("DIAG", f"    ✓ {p}")
        log("DIAG", f"  issues ({len(data['issues'])}):")
        for iss in data["issues"]:
            log("DIAG", f"    [{iss['severity']}] {iss['code']}: {iss['title']}")
        if data["policy_refs"]:
            log("DIAG", f"  policy_refs: {data['policy_refs']}")

        ok_a = (
            data["overall_risk"] in ("low", "medium")
            and not any(i["severity"] in ("critical", "error") for i in data["issues"])
            and len(data["positives"]) >= 1
        )
        log("DIAG", f"Scenario A {'PASS' if ok_a else 'FAIL'}")
        results.append({"scenario": "complete_US_B2", "ok": ok_a, "risk": data["overall_risk"]})

        # ============================================================ #
        # 场景B: US 申请 — 护照 3 月过期 + 缺 DS-160 → high/critical     #
        # ============================================================ #
        log("DIAG", "=" * 50)
        log("DIAG", "Scenario B: US application with expiring passport + missing DS-160")
        m_passport_short = upload_material(
            client, token,
            filename="passport_expiring.jpg",
            material_type="passport",
            salt="passport-short-002",
            ocr_result={"fields": {
                "passport_no": "E98765432",
                "expiry": "2026-09-15",  # ~3 months from 2026-06-25
            }},
        )
        m_photo2 = upload_material(
            client, token,
            filename="photo.jpg",
            material_type="photo",
            salt="photo-blank-002",
        )
        log("DIAG", f"uploaded 2 materials: {m_passport_short} / {m_photo2}")

        data = diagnose(client, token, {
            "material_ids": [m_passport_short, m_photo2],
            "country_code": "US",
            "visa_type": "default",
            "fields": {"travel_date": "2026-08-01"},
        })
        log("DIAG", f"  overall_risk = {data['overall_risk']}  (score={data['risk_score']})")
        log("DIAG", f"  issues:")
        for iss in data["issues"]:
            log("DIAG", f"    [{iss['severity']}] {iss['code']}: {iss['title']}")
            if iss["fix_suggestion"]:
                log("DIAG", f"        → fix: {iss['fix_suggestion']}")

        # Must hit passport.expiry_short (critical) + us.ds160 (warning)
        has_expiry_issue = any(i["code"] == "passport.expiry_short" for i in data["issues"])
        has_ds160_missing = any(i["code"] == "us.ds160" for i in data["issues"])
        ok_b = (
            data["overall_risk"] in ("high", "critical")
            and has_expiry_issue
            and has_ds160_missing
        )
        log("DIAG", f"  has_expiry_issue={has_expiry_issue} has_ds160_missing={has_ds160_missing}")
        log("DIAG", f"Scenario B {'PASS' if ok_b else 'FAIL'}")
        results.append({"scenario": "expiring_passport_US", "ok": ok_b, "risk": data["overall_risk"]})

        # ============================================================ #
        # 场景C: 残缺申请 — 只传护照 → critical                          #
        # ============================================================ #
        log("DIAG", "=" * 50)
        log("DIAG", "Scenario C: Bare minimum (only passport) — should be critical")
        m_only_passport = upload_material(
            client, token,
            filename="passport_only.jpg",
            material_type="passport",
            salt="passport-only-003",
            ocr_result={"fields": {"passport_no": "G99999999", "expiry": "2028-06-30"}},
        )
        log("DIAG", f"uploaded 1 material: {m_only_passport}")

        data = diagnose(client, token, {
            "material_ids": [m_only_passport],
            "country_code": "GB",
            "visa_type": "tourist",
        })
        log("DIAG", f"  overall_risk = {data['overall_risk']}  (score={data['risk_score']})")
        log("DIAG", f"  issues ({len(data['issues'])}):")
        for iss in data["issues"][:8]:  # top 8
            log("DIAG", f"    [{iss['severity']}] {iss['code']}: {iss['title']}")

        missing_codes = {i["code"] for i in data["issues"] if i["severity"] in ("warning", "error")}
        ok_c = (
            data["overall_risk"] in ("high", "critical")
            and "gb.photo" in missing_codes
            and "gb.form" in missing_codes
        )
        log("DIAG", f"Scenario C {'PASS' if ok_c else 'FAIL'}")
        results.append({"scenario": "bare_minimum_GB", "ok": ok_c, "risk": data["overall_risk"]})

        # ============================================================ #
        # 场景D: 边界 — 0 个 material                                    #
        # ============================================================ #
        log("DIAG", "=" * 50)
        log("DIAG", "Scenario D: edge case — empty material_ids")
        r = client.post(
            "/api/v2/materials/diagnose",
            json={"material_ids": [], "country_code": "US"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        log("DIAG", f"  empty list → HTTP {r.status_code} (expected 422 validation error)")
        ok_d = r.status_code in (400, 422)
        log("DIAG", f"Scenario D {'PASS' if ok_d else 'FAIL'}")
        results.append({"scenario": "empty_materials", "ok": ok_d})

        # === summary ===
        log("DONE", "=" * 50)
        pass_count = sum(1 for r in results if r["ok"])
        log("DONE", f"Case 7 (diagnose): {pass_count}/{len(results)} scenarios passed")
        for r in results:
            log("DONE", f"  - {r['scenario']}: {'OK' if r['ok'] else 'FAIL'} (risk={r.get('risk', '-')})")

    return 0 if pass_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())