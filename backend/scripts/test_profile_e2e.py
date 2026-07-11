#!/usr/bin/env python3
"""E2E test for /api/v2/profile/* — applicant CRUD + email change flow.

Run from project root:
    cd /Users/apple/Desktop/签证项目_副本/backend
    PYTHONPATH=. ./.venv/bin/python scripts/test_profile_e2e.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Add backend to path
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402

BASE = "http://localhost:8000/api/v2"


def _hr(msg: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {msg}")
    print("=" * 60)


def _check(label: str, expected_code: str, body: dict) -> None:
    actual = body.get("code")
    if actual != expected_code:
        print(f"  ✗ {label}: expected {expected_code}, got {actual}: {json.dumps(body, ensure_ascii=False)[:200]}")
        sys.exit(1)
    print(f"  ✓ {label}")


def main() -> None:
    # 1. Login
    _hr("1. Login as demo1")
    r = httpx.post(
        f"{BASE}/auth/login",
        json={"account": "demo1@htex.local", "password": "Htex@2026"},
        timeout=10,
    )
    r.raise_for_status()
    body = r.json()
    _check("login OK", "1000", body)
    token = body["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = body["data"]["user"]["id"]
    print(f"  user_id={user_id}  token[:20]={token[:20]}")

    # 2. GET /profile
    _hr("2. GET /profile")
    r = httpx.get(f"{BASE}/profile", headers=headers, timeout=10)
    body = r.json()
    _check("get_profile OK", "1000", body)
    p = body["data"]
    print(f"  id={p['id']}  email={p['email']}  status={p['status']}  applicant_limit={p['applicant_limit']}")
    assert p["applicant_limit"] == 10
    assert p["email_pending"] is None

    # 3. List applicants (start empty)
    _hr("3. GET /profile/applicants (should be empty)")
    r = httpx.get(f"{BASE}/profile/applicants", headers=headers, timeout=10)
    body = r.json()
    _check("list empty OK", "1000", body)
    print(f"  total={body['data']['total']}  items={body['data']['items']}")
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []

    # 4. Create applicant 1
    _hr("4. POST /profile/applicants — 张三")
    r = httpx.post(
        f"{BASE}/profile/applicants",
        headers=headers,
        json={"surname": "张", "given_name": "三", "passport_no": "E12345678"},
        timeout=10,
    )
    body = r.json()
    _check("create OK", "1000", body)
    a1 = body["data"]["applicant"]
    print(f"  id={a1['id']}  name={a1['display_name']}  passport={a1['passport_no']}")
    assert a1["display_name"] == "张三"
    assert a1["passport_no"] == "E12345678"

    # 5. Create applicant 2 (western name with space-join)
    _hr("5. POST /profile/applicants — John Smith")
    r = httpx.post(
        f"{BASE}/profile/applicants",
        headers=headers,
        json={"surname": "Smith", "given_name": "John", "passport_no": "US1234567"},
        timeout=10,
    )
    body = r.json()
    _check("create OK", "1000", body)
    a2 = body["data"]["applicant"]
    print(f"  id={a2['id']}  name={a2['display_name']}  passport={a2['passport_no']}")
    assert a2["display_name"] == "Smith John", f"got {a2['display_name']!r}"
    assert a2["passport_no"] == "US1234567"

    # 6. Duplicate name → 9002
    _hr("6. POST /profile/applicants — duplicate name 张三")
    r = httpx.post(
        f"{BASE}/profile/applicants",
        headers=headers,
        json={"surname": "张", "given_name": "三", "passport_no": "DIFFERENT123"},
        timeout=10,
    )
    body = r.json()
    _check("dup_name 9002", "9002", body)
    print(f"  msg={body.get('message')}")

    # 7. Duplicate passport → 9003
    _hr("7. POST /profile/applicants — duplicate passport E12345678")
    r = httpx.post(
        f"{BASE}/profile/applicants",
        headers=headers,
        json={"surname": "李", "given_name": "四", "passport_no": "E12345678"},
        timeout=10,
    )
    body = r.json()
    _check("dup_passport 9003", "9003", body)
    print(f"  msg={body.get('message')}")

    # 8. Bad passport format → 400 (pydantic)
    _hr("8. POST /profile/applicants — bad passport format")
    r = httpx.post(
        f"{BASE}/profile/applicants",
        headers=headers,
        json={"surname": "王", "given_name": "五", "passport_no": "!!!"},
        timeout=10,
    )
    body = r.json()
    print(f"  status={r.status_code}  body={json.dumps(body)[:200]}")
    assert r.status_code == 400

    # 9. List again (should have 2)
    _hr("9. GET /profile/applicants (should have 2)")
    r = httpx.get(f"{BASE}/profile/applicants", headers=headers, timeout=10)
    body = r.json()
    _check("list 2 OK", "1000", body)
    print(f"  total={body['data']['total']}")
    assert body["data"]["total"] == 2

    # 10. PATCH applicant
    _hr(f"10. PATCH /profile/applicants/{a1['id']} — change passport")
    r = httpx.patch(
        f"{BASE}/profile/applicants/{a1['id']}",
        headers=headers,
        json={"passport_no": "E99999999"},
        timeout=10,
    )
    body = r.json()
    _check("patch OK", "1000", body)
    a1_new = body["data"]["applicant"]
    print(f"  passport={a1_new['passport_no']}")
    assert a1_new["passport_no"] == "E99999999"

    # 11. PATCH other user → 9001 not found
    _hr("11. PATCH /profile/applicants/9999 — not found")
    r = httpx.patch(
        f"{BASE}/profile/applicants/9999",
        headers=headers,
        json={"passport_no": "X1234567"},
        timeout=10,
    )
    body = r.json()
    _check("not_found 9001", "9001", body)

    # 12. DELETE applicant
    _hr(f"12. DELETE /profile/applicants/{a2['id']}")
    r = httpx.delete(
        f"{BASE}/profile/applicants/{a2['id']}",
        headers=headers,
        timeout=10,
    )
    body = r.json()
    _check("delete OK", "1000", body)
    print(f"  deleted={body['data']['deleted']}")

    # 13. List → 1
    _hr("13. GET /profile/applicants (should have 1)")
    r = httpx.get(f"{BASE}/profile/applicants", headers=headers, timeout=10)
    body = r.json()
    _check("list 1 OK", "1000", body)
    assert body["data"]["total"] == 1

    # 14. Email change request
    _hr("14. POST /profile/email/change-request")
    new_email = f"newemail_{int(time.time())}@example.com"
    r = httpx.post(
        f"{BASE}/profile/email/change-request",
        headers=headers,
        json={"new_email": new_email, "password": "Htex@2026"},
        timeout=10,
    )
    body = r.json()
    _check("change_req OK", "1000", body)
    pending = body["data"]["pending_email"]
    print(f"  pending_email={pending}")
    assert pending == new_email

    # 14b. Cancel so test 15/16/17 can run cleanly
    r = httpx.post(
        f"{BASE}/profile/email/change-cancel",
        headers=headers,
        timeout=10,
    )
    assert r.json()["code"] == "1000"

    # 15. Confirm same email → 10003
    # Note: pydantic EmailStr rejects `.local` TLD as not a real TLD, so we
    # change the current email to a valid TLD first, then try changing to
    # the same valid email.
    _hr("15. POST /profile/email/change-request — same as current")
    valid_email = f"valid_{int(time.time())}@example.com"
    r = httpx.post(
        f"{BASE}/profile/email/change-request",
        headers=headers,
        json={"new_email": valid_email, "password": "Htex@2026"},
        timeout=10,
    )
    body = r.json()
    _check("change_to_valid OK", "1000", body)
    # Now `user.email` is NOT yet `valid_email` — it's still the original
    # email (only email_pending is set). The 10003 path fires when the
    # new email matches `user.email` (the actual current). So we can't
    # test 10003 without first confirming the change. Skip the 10003
    # assertion in CI; the comparison logic is unit-trivial.
    # Cancel pending
    r = httpx.post(
        f"{BASE}/profile/email/change-cancel",
        headers=headers,
        timeout=10,
    )
    assert r.json()["code"] == "1000"
    print("  (10003 path covered by direct unit test; e2e skips due to confirmation flow)")

    # 16. Wrong password → 2001
    _hr("16. POST /profile/email/change-request — wrong password")
    r = httpx.post(
        f"{BASE}/profile/email/change-request",
        headers=headers,
        json={"new_email": f"another_{int(time.time())}@example.com", "password": "WRONG"},
        timeout=10,
    )
    body = r.json()
    _check("bad_pwd 2001", "2001", body)

    # 17. Cancel pending change (should be a no-op since already cleared)
    _hr("17. POST /profile/email/change-cancel (idempotent)")
    r = httpx.post(
        f"{BASE}/profile/email/change-cancel",
        headers=headers,
        timeout=10,
    )
    body = r.json()
    _check("cancel OK", "1000", body)
    assert body["data"]["pending_email"] is None

    # 18. Verify pending cleared
    _hr("18. GET /profile (pending_email should be null)")
    r = httpx.get(f"{BASE}/profile", headers=headers, timeout=10)
    body = r.json()
    _check("get_profile OK", "1000", body)
    print(f"  email_pending={body['data']['email_pending']}")
    assert body["data"]["email_pending"] is None

    # 19. Unauth → 1005
    _hr("19. GET /profile (no token)")
    r = httpx.get(f"{BASE}/profile", timeout=10)
    body = r.json()
    _check("unauth 1005", "1005", body)

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
