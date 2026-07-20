"""Case 4: RAG 自动更新官网信息真业务流.

流程:
  1. admin 登录 → admin token
  2. 调用 POST /api/v2/rag/refresh (admin) — 刷新产品线 curated 内容
  3. 普通用户登录 → user token
  4. 调用 GET /api/v2/rag/sources — 列出 sources + last_refresh_at
  5. 调用 POST /api/v2/rag/query (产品线案例):
     - US 美国签证费用 / 材料
     - FR 申根签证申请流程
     - AU 澳大利亚旅游签材料
  6. 验证 refresh + query 返回有用结果
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
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


def main():
    phone = "139" + str(int(time.time()))[-8:]
    log("START", f"phone={phone}")

    with httpx.Client(base_url=BASE, timeout=60) as client:
        # === 1. admin login ===
        log("ADMIN", "login...")
        admin_token = admin_login(client)

        # === 2. refresh RAG (admin) ===
        log("REFRESH", "POST /api/v2/rag/refresh (no country filter — refresh all)")
        t0 = time.time()
        r = client.post("/api/v2/rag/refresh", headers={"Authorization": f"Bearer {admin_token}"})
        dt = time.time() - t0
        log("REFRESH", f"HTTP {r.status_code} in {dt:.1f}s")
        if r.status_code != 200:
            log("REFRESH", f"FAIL: {r.text[:500]}")
            return 1
        body = r.json()["data"]
        log("REFRESH", f"refreshed={body['refreshed']}, errors={body['errors']}")
        for item in body["items"]:
            log("REFRESH", f"  [{item.get('status')}] {item}")

        # === 3. user login ===
        log("USER", "register+login...")
        user_token = user_register_login(client, phone)
        log("USER", "user token OK")

        # === 4. list sources ===
        log("SOURCES", "GET /api/v2/rag/sources")
        r = client.get("/api/v2/rag/sources", headers={"Authorization": f"Bearer {user_token}"})
        log("SOURCES", f"HTTP {r.status_code}")
        sources = r.json()["data"]
        log("SOURCES", f"{len(sources)} sources configured:")
        for s in sources:
            log("SOURCES", f"  [{s['country_code']}] {s['name']} (last_status={s['last_status']}, url={s['url']})")

        # === 5. query (3 案例) ===
        queries = [
            ("美国 B1/B2 签证费用多少", "US"),
            ("美国签证需要什么材料", "US"),
            ("申根签证申请流程", "FR"),
            ("澳大利亚旅游签材料清单", "AU"),
        ]
        results = []
        for q, cc in queries:
            log("QUERY", f"--- '{q}' (country={cc}) ---")
            t0 = time.time()
            r = client.post("/api/v2/rag/query",
                json={"query": q, "country_code": cc, "top_k": 3},
                headers={"Authorization": f"Bearer {user_token}"},
            )
            dt = time.time() - t0
            log("QUERY", f"HTTP {r.status_code} in {dt:.2f}s")
            if r.status_code != 200:
                log("QUERY", f"FAIL: {r.text[:300]}")
                results.append({"query": q, "ok": False})
                continue
            data = r.json()["data"]
            log("QUERY", f"answer: {data['answer'][:200]}")
            log("QUERY", f"chunks: {len(data['chunks'])}")
            for i, ch in enumerate(data["chunks"]):
                log("QUERY", f"  [{i+1}] score={ch['score']:.3f} src={ch['source_name']}: {ch['snippet'][:100]}")
            ok = bool(data.get("answer")) and len(data.get("chunks", [])) > 0
            results.append({"query": q, "ok": ok, "country": cc, "n_chunks": len(data.get("chunks", []))})

        # === 6. summary ===
        log("DONE", "=" * 50)
        ok = sum(1 for r in results if r.get("ok"))
        log("DONE", f"RAG 真业务流: {ok}/{len(queries)} query 返回有用结果")
        log("DONE", f"refresh: {body['refreshed']} sources ok, {body['errors']} errors")
        return 0 if ok == len(queries) and body["refreshed"] >= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
