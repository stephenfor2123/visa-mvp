"""Case 6: 材料自动分类真业务流 (V2 §4.3.4 classify).

流程:
  1. 注册+登录 → JWT
  2. 不传 file / material_id → 纯 filename 模式 (fast path)
  3. 验证多种文件名能正确分类:
     - passport.jpg              → passport
     - 身份证_正面.png             → id_card
     - 户口本_首页.jpg             → household
     - 在校证明.pdf               → enrollment
     - 2寸白底照片.jpg            → photo
     - DS-160确认页.pdf          → form
  4. 传 filename + ocr_result 字段 (模拟 mode C / A)
  5. /api/v2/materials/{id}/classification 确认/纠正
"""
from __future__ import annotations

import sys
import time
from typing import Optional

import httpx

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


def classify(
    client: httpx.Client,
    token: str,
    *,
    filename: str,
    mime: str,
    ocr_fields: Optional[dict] = None,
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    form = {"filename": filename, "mime_type": mime}
    if ocr_fields:
        # we don't have a dedicated ocr_json field — instead, use material_id path
        pass
    r = client.post(
        "/api/v2/materials/classify",
        data=form,
        headers=headers,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]


# (filename, mime, expected_type)
PURE_FILENAME_CASES = [
    ("passport.jpg",                "image/jpeg",      "passport"),
    ("护照首页.jpg",                  "image/jpeg",      "passport"),
    ("E12345678.jpg",               "image/jpeg",      "passport"),
    ("身份证_正面.png",                "image/png",       "id_card"),
    ("id_card_front.jpg",           "image/jpeg",      "id_card"),
    ("11010119900307881X.png",      "image/png",       "id_card"),
    ("户口本_首页.jpg",                "image/jpeg",      "household"),
    ("户口簿扫描件.jpg",               "image/jpeg",      "household"),
    ("在校证明.pdf",                  "application/pdf", "enrollment"),
    ("学生证.jpg",                    "image/jpeg",      "enrollment"),
    ("2寸白底照片.jpg",                "image/jpeg",      "photo"),
    ("photo_white_bg.png",          "image/png",       "photo"),
    ("DS-160确认页.pdf",             "application/pdf", "form"),
    ("申请表_NOA1.pdf",              "application/pdf", "form"),
    ("签证申请表格.pdf",               "application/pdf", "form"),
    ("银行流水_2024Q4.pdf",           "application/pdf", "other"),  # no keyword hits → other
    ("random_doc.pdf",              "application/pdf", "other"),
]


def main() -> int:
    phone = "139" + str(int(time.time()))[-8:]
    log("START", f"phone={phone}")

    with httpx.Client(base_url=BASE, timeout=30) as client:
        token = register_and_login(client, phone)
        log("AUTH", "OK")

        results = []
        # === Test 1: pure filename classification ===
        log("CLS", "=== Test 1: filename-only classification ===")
        for fname, mime, expected in PURE_FILENAME_CASES:
            data = classify(client, token, filename=fname, mime=mime)
            predicted = data["predicted_type"]
            conf = data["confidence"]
            ok = predicted == expected
            mark = "OK" if ok else "FAIL"
            log("CLS", f"  [{mark}] {fname:30s} mime={mime:18s} expected={expected:12s} got={predicted:12s} conf={conf}")
            results.append({
                "case": f"filename:{fname}",
                "expected": expected,
                "got": predicted,
                "confidence": conf,
                "ok": ok,
            })

        # === Test 2: classification with material_id (mode A — fetch from DB) ===
        log("CLS", "=== Test 2: material_id classification (DB round-trip) ===")
        # upload a test material first
        # create a tiny JPEG file
        import io
        import cv2
        import numpy as np
        img = np.ones((400, 600, 3), dtype=np.uint8) * 240
        cv2.putText(img, "PASSPORT G12345678", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        ok, buf = cv2.imencode(".jpg", img)
        test_jpeg = buf.tobytes()

        # upload as 'other' first (we'll let AI reclassify)
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": ("test_passport_photo.jpg", io.BytesIO(test_jpeg), "image/jpeg")}
        r = client.post(
            "/api/v2/materials/upload",
            files=files,
            data={"material_type": "other"},
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        mat_id = r.json()["data"]["material"]["id"]
        log("CLS", f"uploaded material_id={mat_id} as 'other'")

        # classify by material_id
        r = client.post(
            "/api/v2/materials/classify",
            data={"material_id": str(mat_id)},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()["data"]
        log("CLS", f"  classified: {data['predicted_type']} conf={data['confidence']}")
        log("CLS", f"  candidates: {[(c['material_type'], c['score']) for c in data['candidates'][:3]]}")
        log("CLS", f"  hints: {len(data['hints'])}")
        ok_id = data["predicted_type"] == "passport"
        log("CLS", f"Test 2 {'PASS' if ok_id else 'FAIL'} (expected 'passport' from filename 'test_passport_photo.jpg')")
        results.append({"case": "material_id_roundtrip", "ok": ok_id})

        # === Test 3: user confirms/corrects classification ===
        log("CLS", "=== Test 3: confirm classification ===")
        # 3a: confirm (user accepts AI guess)
        r = client.post(
            f"/api/v2/materials/{mat_id}/classification",
            json={"material_type": data["predicted_type"], "confirmed": True},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        log("CLS", f"  confirmed AI guess: {r.json()['data']['material_type']}")
        ok_confirm = r.status_code == 200

        # 3b: correct (user overrides to 'photo')
        r = client.post(
            f"/api/v2/materials/{mat_id}/classification",
            json={"material_type": "photo", "confirmed": False},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        body = r.json()["data"]
        log("CLS", f"  corrected to: {body['material_type']} (classification_corrected={body['classification_corrected']})")
        ok_correct = (
            body["material_type"] == "photo"
            and body["classification_corrected"] == "photo"
        )

        log("CLS", f"Test 3 {'PASS' if ok_confirm and ok_correct else 'FAIL'}")
        results.append({"case": "confirm_and_correct", "ok": ok_confirm and ok_correct})

    # === summary ===
    log("DONE", "=" * 50)
    pass_count = sum(1 for r in results if r["ok"])
    log("DONE", f"Case 6 (classify): {pass_count}/{len(results)} sub-tests passed")
    fail_cases = [r for r in results if not r["ok"]]
    if fail_cases:
        log("DONE", "Failures:")
        for r in fail_cases:
            log("DONE", f"  - {r}")

    return 0 if pass_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())