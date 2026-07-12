#!/usr/bin/env python3
"""One-shot: send a registration verification email via Resend.

Usage (key must be in backend/.env, never on CLI):
  cd backend && .venv/bin/python scripts/test_send_verification_email.py stephenfor2123@gmail.com
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.services.email_service import VerificationCodeEmail, send_verification_code_email


def main() -> int:
    to = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not to or "@" not in to:
        print("Usage: python scripts/test_send_verification_email.py <email>")
        return 1

    get_settings.cache_clear()
    settings = get_settings()

    if not settings.resend_api_key.strip():
        print("ERROR: RESEND_API_KEY is empty. Add it to backend/.env and retry.")
        return 1

    code = f"{secrets.randbelow(1_000_000):06d}"
    print(f"backend={settings.email_backend}")
    print(f"from={settings.email_from}")
    print(f"to={to}")
    print(f"code={code}  (also check inbox)")

    ok = send_verification_code_email(VerificationCodeEmail(to_email=to, code=code))
    if ok:
        print("OK: email dispatched — check Resend Emails/Logs and your inbox.")
        return 0
    print("FAIL: send_verification_code_email returned False — check backend logs.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
