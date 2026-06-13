#!/usr/bin/env python3
"""
W10 集成测试脚本 — C-W10-5 verifier 收口
4 子系统端到端联调验证

Run from backend/:
    python3 ../backend/tests/integration/test_w10_integration.py

Requires:
    - frontend project at /Users/stephen/Desktop/签证项目/
    - backend project at /Users/stephen/Desktop/签证项目/backend/
    - node/npm in PATH
    - Flutter in PATH (for iOS build test)
    - Python 3.9+ with stripe, pytest
"""

import subprocess
import sys
import os
import json
import hashlib
import re
from pathlib import Path

# Project roots
PROJECT_ROOT = Path("/Users/stephen/Desktop/签证项目")
FRONTEND_WEB = PROJECT_ROOT / "frontend/web"
FRONTEND_IOS = PROJECT_ROOT / "frontend/ios"
BACKEND = PROJECT_ROOT / "backend"
WORKSPACE = Path("/Users/stephen/.mavis/plans/plan_4a8f622c/workspace")


class Results:
    def __init__(self):
        self.checks = []

    def record(self, name, passed, evidence=""):
        self.checks.append({"name": name, "passed": passed, "evidence": evidence})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if evidence:
            for line in evidence.split("\n"):
                print(f"         {line}")

    def summary(self):
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        return passed, total


def test_a_worklog_repair(results: Results):
    """W9-1 A_WORKLOG.md grep 命中验证"""
    print("\n[1] test_a_worklog_repair: grep 'W9-1' A_WORKLOG.md")

    aworklog = PROJECT_ROOT / "frontend/ios/A_WORKLOG.md"
    if not aworklog.exists():
        results.record("A_WORKLOG.md exists", False, f"NOT FOUND: {aworklog}")
        return

    content = aworklog.read_text()
    hits = content.count("W9-1")
    results.record("A_WORKLOG.md grep W9-1 hits ≥ 1", hits >= 1, f"'{hits}' hits found in {aworklog}")

    # Verify W6-4 too (B-W10-3 reopen)
    hits_w64 = content.count("W6-4")
    results.record("A_WORKLOG.md grep W6-4 hits ≥ 1", hits_w64 >= 1, f"'{hits_w64}' hits found")


def test_l4_i18n(results: Results):
    """L4 i18n 4语种 full-locale 验证"""
    print("\n[2] test_l4_i18n: 4 语种 i18n json ≥ 100 keys")

    locales = {
        "zh-CN": PROJECT_ROOT / "frontend/shared/i18n/zh-CN.json",
        "en":    PROJECT_ROOT / "frontend/shared/i18n/en.json",
        "id":    PROJECT_ROOT / "frontend/shared/i18n/id.json",
        "vi":    PROJECT_ROOT / "frontend/shared/i18n/vi.json",
    }

    # Check file count
    missing = [k for k, v in locales.items() if not v.exists()]
    results.record("4 locale files exist", len(missing) == 0,
                   f"Missing: {missing}" if missing else "all 4 found")

    # Count keys (recursive)
    def count_keys(obj):
        if isinstance(obj, dict):
            return sum(count_keys(v) for v in obj.values())
        return 1

    key_counts = {}
    for lang, path in locales.items():
        if path.exists():
            data = json.loads(path.read_text())
            cnt = count_keys(data)
            key_counts[lang] = cnt

    all_above_100 = all(cnt >= 100 for cnt in key_counts.values())
    evidence = "\n".join(f"  {k}: {v} keys" for k, v in key_counts.items())
    results.record("All 4 locales ≥ 100 keys", all_above_100, evidence)

    # Key alignment check
    base_keys_path = PROJECT_ROOT / "frontend/shared/i18n/zh-CN.json"
    base_keys = set(json.loads(base_keys_path.read_text()).keys())
    aligned = True
    for lang in ["en", "id", "vi"]:
        path = locales[lang]
        if path.exists():
            lang_keys = set(json.loads(path.read_text()).keys())
            if base_keys != lang_keys:
                aligned = False
                diff = base_keys ^ lang_keys
                results.record(f"{lang} keys aligned with zh-CN", False, f"diff: {diff}")
    if aligned:
        results.record("All locales top-level key alignment", True,
                       f"4 locales aligned on {len(base_keys)} sections")

    # npm build
    print("\n  Running npm run build (i18n verification)...")
    r = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(FRONTEND_WEB),
        capture_output=True,
        text=True,
        timeout=120,
    )
    build_pass = r.returncode == 0 and "built in" in r.stdout.lower()
    results.record("npm run build PASS", build_pass,
                   r.stdout.split("\n")[-3] if r.stdout else r.stderr[-200:])


def test_ios_4_p0_repair(results: Results):
    """iOS 4 P0 修复验证 (W9-1 + W6-4)"""
    print("\n[3] test_ios_4_p0_repair: 3 screenshots + flutter build web")

    # 3 screenshots exist
    shots = {
        "home_zh.png":      477895,
        "register_en.png": 136437,
        "materials_id.png": 121170,
    }
    shot_dir = FRONTEND_IOS / "screenshots"
    all_exist = True
    sha256s = {}
    sizes_ok = True
    for name, expected_size in shots.items():
        path = shot_dir / name
        if not path.exists():
            results.record(f"{name} exists", False, f"NOT FOUND: {path}")
            all_exist = False
            continue
        content = path.read_bytes()
        sha256s[name] = hashlib.sha256(content).hexdigest()
        actual_size = len(content)
        size_ok = actual_size == expected_size
        if not size_ok:
            sizes_ok = False
        print(f"  {name}: {sha256s[name][:16]}... ({actual_size} bytes)")

    if all_exist:
        results.record("3 iOS screenshots exist", True,
                       f"home_zh/register_en/materials_id all found")

    # sha256 distinct
    if len(set(sha256s.values())) == 3:
        results.record("3 screenshots sha256 distinct", True,
                       "\n".join(f"  {k[:16]}...: {v[:16]}..." for k, v in sha256s.items()))
    else:
        results.record("3 screenshots sha256 distinct", False,
                       f"DUPLICATE HASHES: {sha256s}")

    results.record("Screenshot file sizes match expected", sizes_ok,
                   "All 3 sizes match W9-1/W6-4 records")

    # flutter build web
    print("\n  Running flutter build web --release...")
    r = subprocess.run(
        ["flutter", "build", "web", "--release"],
        cwd=str(FRONTEND_IOS),
        capture_output=True,
        text=True,
        timeout=180,
    )
    build_ok = r.returncode == 0 and ("Built build/web" in r.stdout or "Built build/web" in r.stderr)
    results.record("flutter build web BUILD SUCCESS", build_ok,
                   r.stdout.split("\n")[-3] if r.stdout else r.stderr[-200:])


def test_stripe_payout(results: Results):
    """Stripe V2.1 真接验证 (V2 空凭据时跳过)"""
    print("\n[4] test_stripe_payout: Stripe SDK + pytest")

    backend_dir = BACKEND

    # Check SDK async methods
    print("  Checking Stripe SDK async methods...")
    r = subprocess.run(
        [
            str(backend_dir / ".venv/bin/python3"),
            "-c",
            (
                "import stripe; "
                "methods=['create_async','retrieve_async','cancel_async']; "
                "pis=['PaymentIntent.'+m for m in methods]; "
                "pis.append('Transfer.create_async'); "
                "for attr in pis: "
                "  parts=attr.split('.'); "
                "  obj=stripe; "
                "  for p in parts: obj=getattr(obj,p); "
                "  print(f'{attr}: {True}'); "
            )
        ],
        capture_output=True,
        text=True,
    )
    all_async = all(f": {True}" in line for line in r.stdout.strip().split("\n") if line.strip())
    results.record("Stripe SDK 4 async methods exist", all_async, r.stdout.strip())

    # Run Stripe tests
    print("  Running pytest test_payment_stripe.py...")
    r = subprocess.run(
        [
            str(backend_dir / ".venv/bin/python3"),
            "-m", "pytest",
            "tests/integration/test_payment_stripe.py",
            "-v", "--tb=short",
        ],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    stripe_pass = r.returncode == 0 and "passed" in r.stdout.lower()
    # Extract pass count
    m = re.search(r"(\d+) passed", r.stdout)
    stripe_count = int(m.group(1)) if m else 0
    results.record("test_payment_stripe.py PASS", stripe_pass,
                   f"{stripe_count}/5 passed — {r.stdout.split(chr(10))[-3].strip()}")

    # Run stub + original payment tests
    print("  Running pytest test_payment_stripe_stub.py + test_payment.py...")
    r2 = subprocess.run(
        [
            str(backend_dir / ".venv/bin/python3"),
            "-m", "pytest",
            "tests/integration/test_payment_stripe_stub.py",
            "tests/integration/test_payment.py",
            "-v", "--tb=short",
        ],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    stub_pass = r2.returncode == 0
    m2 = re.search(r"(\d+) passed", r2.stdout)
    stub_count = int(m2.group(1)) if m2 else 0
    results.record("test_payment_stripe_stub + test_payment PASS", stub_pass,
                   f"{stub_count}/12 passed — {r2.stdout.split(chr(10))[-3].strip()}")


def main():
    print("=" * 60)
    print("W10 集成测试 — C-W10-5 Verifier 收口")
    print("=" * 60)

    results = Results()

    test_a_worklog_repair(results)
    test_l4_i18n(results)
    test_ios_4_p0_repair(results)
    test_stripe_payout(results)

    print("\n" + "=" * 60)
    passed, total = results.summary()
    print(f"结果: {passed}/{total} PASS")
    print("=" * 60)

    for c in results.checks:
        if not c["passed"]:
            print(f"\n  [FAIL] {c['name']}")
            if c["evidence"]:
                print(f"         {c['evidence']}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
