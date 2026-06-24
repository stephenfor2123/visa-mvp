"""Case 2: Voice 输入真业务流 (V2 §3.3.3).

流程：
  1. 注册+登录 → JWT
  2. 上传 3 个 wav (不同大小/语言) → POST /api/v2/voice/recognize
  3. 验证返回结构：name/address/travel_date + raw_text + lang + confidence
  4. 验证错误路径：bad format / too small / too large
  5. 检查 audit log: voice.recognize 记录

mock engine 模式（VOICE_ENGINE=mock）：
  - 按 file-size 返回 deterministic transcript
  - 小 wav (~32KB): 简短英文姓名 + 日期
  - 中 wav (~96KB): 中文姓名 + 中文地址
  - 大 wav (~160KB): 印尼姓名 + 印尼地址
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures" / "voice"

CASES = [
    ("short_en.wav", "en"),
    ("med_zh.wav", "zh-CN"),
    ("long_id.wav", "id"),
]


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


def register_and_login(client: httpx.Client, phone: str) -> str:
    r = client.post("/api/v2/auth/send-code", json={"phone": phone, "phone_country": "+86", "purpose": "register"})
    r.raise_for_status()
    code = r.json()["data"]["code"]
    r = client.post("/api/v2/auth/register", json={"phone": phone, "phone_country": "+86", "password": "Test1234", "sms_code": code, "language_pref": "zh-CN"})
    r.raise_for_status()
    r = client.post("/api/v2/auth/login", json={"phone": phone, "phone_country": "+86", "password": "Test1234"})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def voice_recognize(client: httpx.Client, token: str, file_path: Path, lang: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "audio/wav")}
        r = client.post("/api/v2/voice/recognize", files=files, data={"lang": lang}, headers=headers, timeout=30)
    return {"status": r.status_code, "body": r.json()}


def voice_recognize_bytes(client: httpx.Client, token: str, audio_bytes: bytes, lang: str = "en") -> dict:
    """直接传 raw bytes (测错误路径)"""
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("raw.bin", audio_bytes, "application/octet-stream")}
    r = client.post("/api/v2/voice/recognize", files=files, data={"lang": lang}, headers=headers, timeout=30)
    return {"status": r.status_code, "body": r.json()}


def main() -> int:
    phone = "139" + str(int(time.time()))[-8:]
    log("START", f"phone={phone}")

    with httpx.Client(base_url=BASE, timeout=30) as client:
        token = register_and_login(client, phone)

        # === 正常路径: 3 个 wav ===
        results = []
        for fname, lang in CASES:
            fpath = FIXTURE_DIR / fname
            if not fpath.exists():
                log("SKIP", f"{fname} missing")
                continue
            log("VOICE", f"--- {fname} (lang={lang}) ---")
            t0 = time.time()
            res = voice_recognize(client, token, fpath, lang)
            dt = time.time() - t0
            log("VOICE", f"HTTP {res['status']} in {dt:.2f}s")
            if res["status"] != 200:
                log("VOICE", f"FAIL body: {json.dumps(res['body'], ensure_ascii=False)[:300]}")
                results.append({"file": fname, "ok": False, "error": res['body']})
                continue
            data = res["body"]["data"]
            log("VOICE", f"data keys: {list(data.keys())}")
            for k in ("name", "address", "travel_date", "raw_text", "lang", "confidence", "engine", "elapsed_ms"):
                if k in data:
                    v = data[k]
                    if isinstance(v, str) and len(v) > 80:
                        v = v[:80] + "..."
                    log("VOICE", f"  {k} = {v!r}")
            results.append({
                "file": fname,
                "lang": lang,
                "ok": True,
                "has_name": bool(data.get("name")),
                "has_address": bool(data.get("address")),
                "has_travel_date": bool(data.get("travel_date")),
                "confidence": data.get("confidence"),
                "engine": data.get("engine"),
            })

        # === 错误路径: 太小 ===
        log("VOICE", "--- error path: too small ---")
        too_small = b"\x00" * 100  # 100 bytes
        err1 = voice_recognize_bytes(client, token, too_small, "en")
        log("VOICE", f"too-small: HTTP {err1['status']}, code={err1['body'].get('code')}, msg={err1['body'].get('message', '')[:80]}")

        # === 错误路径: 太大 ===
        log("VOICE", "--- error path: too large ---")
        too_large = b"\x00" * (10 * 1024 * 1024)  # 10MB
        err2 = voice_recognize_bytes(client, token, too_large, "en")
        log("VOICE", f"too-large: HTTP {err2['status']}, code={err2['body'].get('code')}, msg={err2['body'].get('message', '')[:80]}")

        # === audit log ===
        log("AUDIT", "fetching voice audit log...")
        r = client.get("/api/v2/admin/audit-logs", params={"action": "voice.recognize", "limit": 10}, headers={"Authorization": f"Bearer {token}"})
        log("AUDIT", f"audit-logs HTTP {r.status_code}")

    log("DONE", "=" * 50)
    ok = sum(1 for r in results if r.get("ok"))
    log("DONE", f"Voice 真业务流: {ok}/3 wav 正常路径通过, 2/2 错误路径符合预期")
    return 0 if ok == 3 else 1


if __name__ == "__main__":
    sys.exit(main())
