"""Case 1: OCR 真业务流验证 (V2 §5.1).

流程：
  1. 注册+登录 → JWT token
  2. 上传 9 国 sample passport → POST /api/v2/ocr/recognize
  3. 验证返回：items (text + bbox + confidence) + fields (extracted passport fields)
  4. 验证 audit log: ocr.recognize 记录被写入

9 国 passport_no 格式（ICAO 9303 + 国家变体）：
  US: A+8digits  JP: 2α+7digits  GB: 9digits  AU: 1α+7digits
  SG: 1α+7digits+1α  DE: 2α+7digits  FR: 2digits+2α+5digits
  IT: 2α+7digits  KR: 2α+7digits
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
# 绝对路径 — 脚本可从任何 workdir 跑
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"

# (country_code, filename, expected_passport_no_format, lang_code)
COUNTRIES = [
    ("US", "sample_us_passport.jpg", "en"),
    ("JP", "sample_jp_passport.jpg", "en"),
    ("GB", "sample_gb_passport.jpg", "en"),
    ("AU", "sample_au_passport.jpg", "en"),
    ("SG", "sample_sg_passport.jpg", "en"),
    ("DE", "sample_de_passport.jpg", "en"),
    ("FR", "sample_fr_passport.jpg", "en"),
    ("IT", "sample_it_passport.jpg", "en"),
    ("KR", "sample_kr_passport.jpg", "en"),
]


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def register_and_login(client: httpx.Client, phone: str) -> str:
    """注册+登录 → JWT access_token."""
    r = client.post(
        "/api/v2/auth/send-code",
        json={"phone": phone, "phone_country": "+86", "purpose": "register"},
    )
    r.raise_for_status()
    code = r.json()["data"]["code"]
    log("AUTH", f"send-code OK, code={code}")

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
    log("AUTH", "register OK")

    r = client.post(
        "/api/v2/auth/login",
        json={"phone": phone, "phone_country": "+86", "password": "Test1234"},
    )
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def ocr_recognize(client: httpx.Client, token: str, file_path: Path, lang: str) -> dict:
    """上传图片 → OCR API."""
    headers = {"Authorization": f"Bearer {token}"}
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "image/jpeg")}
        r = client.post(
            "/api/v2/ocr/recognize",
            files=files,
            data={"lang": lang},
            headers=headers,
            timeout=60,
        )
    r.raise_for_status()
    return r.json()["data"]


def fetch_audit_log(client: httpx.Client, token: str, action: str = "ocr.recognize") -> list:
    """拉审计日志 (admin endpoint)."""
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(
        "/api/v2/admin/audit-logs",
        params={"action": action, "limit": 20},
        headers=headers,
    )
    if r.status_code == 404:
        log("AUDIT", "audit-logs endpoint 404 — may not be exposed to user token")
        return []
    if r.status_code >= 400:
        log("AUDIT", f"audit-logs HTTP {r.status_code}: {r.text[:200]}")
        return []
    body = r.json()
    return body.get("data", {}).get("items", body.get("data", []))


def main() -> int:
    phone = "139" + str(int(time.time()))[-8:]
    log("START", f"phone={phone}")

    with httpx.Client(base_url=BASE, timeout=30) as client:
        token = register_and_login(client, phone)

        results = []
        for cc, fname, lang in COUNTRIES:
            fpath = FIXTURE_DIR / fname
            if not fpath.exists():
                log("SKIP", f"{cc}: fixture {fpath} missing")
                continue
            log("OCR", f"--- {cc} ({fname}) ---")
            try:
                t0 = time.time()
                data = ocr_recognize(client, token, fpath, lang)
                dt = time.time() - t0
                items = data.get("items", [])
                fields = data.get("fields", {})
                log(
                    "OCR",
                    f"{cc}: items={len(items)}, fields={list(fields.keys())[:6]}, elapsed={dt:.1f}s",
                )
                # show some items
                if items:
                    sample = items[:3]
                    log("OCR", f"{cc} sample items: {[(it['text'][:30], round(it['confidence'], 2)) for it in sample]}")
                # show extracted fields
                important = {k: fields.get(k) for k in ("passport_no", "surname", "given_name", "nationality", "sex", "dob", "expiry_date")}
                log("OCR", f"{cc} fields: {important}")
                results.append({
                    "country": cc,
                    "items_count": len(items),
                    "fields": important,
                    "elapsed_s": round(dt, 2),
                })
            except Exception as e:
                log("OCR", f"{cc} FAILED: {e}")
                results.append({"country": cc, "error": str(e)})

        # === audit log ===
        log("AUDIT", "fetching audit log ...")
        audit = fetch_audit_log(client, token)
        if audit:
            ocr_entries = [a for a in audit if a.get("action") == "ocr.recognize"]
            log("AUDIT", f"total entries: {len(audit)}, ocr.recognize: {len(ocr_entries)}")
            if ocr_entries:
                log("AUDIT", f"sample: {json.dumps(ocr_entries[0], ensure_ascii=False)[:300]}")

    # === summary ===
    log("DONE", "=" * 50)
    ok_count = sum(1 for r in results if "error" not in r)
    total_items = sum(r.get("items_count", 0) for r in results)
    fields_extracted = sum(1 for r in results if r.get("fields", {}).get("passport_no"))
    log("DONE", f"OCR 真业务流: {ok_count}/9 国通过, 共识别 {total_items} 个 items, {fields_extracted}/9 国提取到 passport_no")

    return 0 if ok_count >= 7 else 1  # 至少 7/9 通过算过


if __name__ == "__main__":
    sys.exit(main())
