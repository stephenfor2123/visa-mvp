#!/usr/bin/env python3
"""
D-VERIFY-RUNNER 1.0 — 7-Step Automated DoD Verification for Plan Handoffs

Usage:
    python tools/d_verify_runner.py --task-id <TASK_ID> [options]

Options:
    --task-id          Task ID (required, e.g. C-W11R-3)
    --screenshots-dir  Directory containing screenshots (default: auto-detect)
    --deliverable-path Path to deliverable.md (default: outputs/<task-id>/deliverable.md)
    --worklog-path     Path to WORKLOG.md (default: workspace/backend/WORKLOG.md)
    --pytest-target    Pytest target (default: tests/integration/test_payment_stripe_stub.py)
    --project-root     Project root (default: auto-detect)
    --frontend-dist    Frontend dist directory (default: frontend/web/dist)
    --json             Output JSON format report
    --verbose          Verbose output

7 Steps:
    Step 1: screenshots sha256 distinct
    Step 2: deliverable.md > 50 bytes
    Step 3: WORKLOG.md has task-id
    Step 4: backend pytest all PASS
    Step 5: alembic upgrade head (no error)
    Step 6: i18n no raw key (grep dist/assets/*.js)
    Step 7: .env / config.yaml readable

Exit codes:
    0  all 7 checks PASS
    1  Step 1 FAIL
    2  Step 2 FAIL
    3  Step 3 FAIL
    4  Step 4 FAIL
    5  Step 5 FAIL
    6  Step 6 FAIL
    7  Step 7 FAIL
    8  usage / arg error
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Data structures ────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    result: str          # PASS / FAIL / SKIP
    detail: str = ""
    exit_code: int = 0

    def to_dict(self) -> dict:
        return {"name": self.name, "result": self.result, "detail": self.detail}


@dataclass
class VerifyReport:
    task_id: str
    checks: list = field(default_factory=list)
    overall: str = "PASS"
    timestamp: str = ""
    project_root: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "checks": [c.to_dict() for c in self.checks],
            "overall": self.overall,
            "timestamp": self.timestamp,
            "project_root": self.project_root,
            "error_message": self.error_message,
        }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def find_project_root() -> str:
    """Find project root: script is at <root>/tools/d_verify_runner.py."""
    return str(Path(__file__).resolve().parents[1])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ─── Step 1: screenshots sha256 distinct ────────────────────────────────────

def check_screenshots(screenshots_dir: str, project_root: str) -> CheckResult:
    if not screenshots_dir:
        return CheckResult("sha256 distinct", "SKIP", "No screenshots dir", 0)

    abs_path = screenshots_dir if os.path.isabs(screenshots_dir) \
               else os.path.join(project_root, screenshots_dir)

    if not os.path.isdir(abs_path):
        return CheckResult("sha256 distinct", "SKIP", f"Dir not found: {abs_path}", 0)

    png_files = list(Path(abs_path).glob("*.png"))
    if not png_files:
        return CheckResult("sha256 distinct", "SKIP", f"No *.png in {abs_path}", 0)

    hashes = {}
    for f in png_files:
        try:
            h = sha256_file(f)
            hashes[h] = str(f)
        except Exception as e:
            return CheckResult("sha256 distinct", "FAIL",
                               f"Hash error {f}: {e}", exit_code=1)

    total = len(png_files)
    distinct = len(hashes)
    if distinct == total:
        return CheckResult("sha256 distinct", "PASS",
                           f"{distinct}/{total} distinct (no collision)", 0)
    else:
        collisions = [h for h, cnt in Counter([sha256_file(f) for f in png_files]).items() if cnt > 1]
        return CheckResult("sha256 distinct", "FAIL",
                           f"Only {distinct}/{total} distinct (collisions: {collisions})", 1)


# ─── Step 2: deliverable.md > 50 bytes ──────────────────────────────────────

def check_deliverable(deliverable_path: str, project_root: str,
                      min_bytes: int = 50, min_lines: int = 10) -> CheckResult:
    abs_path = deliverable_path if os.path.isabs(deliverable_path) \
               else os.path.join(project_root, deliverable_path)

    if not os.path.isfile(abs_path):
        return CheckResult("deliverable > 50B", "FAIL",
                           f"File not found: {abs_path}", 2)

    file_size = os.path.getsize(abs_path)
    if file_size == 0:
        return CheckResult("deliverable > 50B", "FAIL",
                           f"Empty file: {abs_path}", 2)

    with open(abs_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if file_size < min_bytes:
        return CheckResult("deliverable > 50B", "FAIL",
                           f"Only {file_size}B (< {min_bytes}): {abs_path}", 2)

    if len(lines) < min_lines:
        return CheckResult("deliverable > 50B", "FAIL",
                           f"Only {len(lines)} lines (< {min_lines}): {abs_path}", 2)

    return CheckResult("deliverable > 50B", "PASS",
                       f"{file_size}B / {len(lines)} lines ({abs_path})", 0)


# ─── Step 3: WORKLOG has task-id ─────────────────────────────────────────────

def check_worklog(worklog_path: str, task_id: str, project_root: str) -> CheckResult:
    abs_path = worklog_path if os.path.isabs(worklog_path) \
               else os.path.join(project_root, worklog_path)

    if not os.path.isfile(abs_path):
        return CheckResult("WORKLOG grep hit", "FAIL",
                           f"WORKLOG not found: {abs_path}", 3)

    hits = 0
    with open(abs_path, "r", encoding="utf-8") as f:
        for line in f:
            if task_id in line:
                hits += 1

    if hits < 1:
        return CheckResult("WORKLOG grep hit", "FAIL",
                           f"No '{task_id}' in {abs_path}", 3)

    return CheckResult("WORKLOG grep hit", "PASS",
                       f"{hits} line(s) mention {task_id}", 0)


# ─── Step 4: backend pytest PASS ─────────────────────────────────────────────

def check_pytest(pytest_target: str, project_root: str) -> CheckResult:
    backend_dir = os.path.join(project_root, "backend")
    if not os.path.isdir(backend_dir):
        return CheckResult("backend pytest", "FAIL",
                           f"Backend dir not found: {backend_dir}", 4)

    venv_pytest = os.path.join(backend_dir, ".venv", "bin", "pytest")
    pytest_bin = venv_pytest if (os.path.isfile(venv_pytest) and os.access(venv_pytest, os.X_OK)) \
                 else "pytest"

    try:
        result = subprocess.run(
            [pytest_bin, pytest_target, "--tb=line", "-q"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )
        output = result.stdout + result.stderr
        last_lines = "\n".join(output.splitlines()[-20:])

        passed_match = None
        for line in output.splitlines():
            if "passed" in line and any(c.isdigit() for c in line):
                passed_match = line.strip()
                break

        if result.returncode == 0 and passed_match:
            return CheckResult("backend pytest", "PASS", passed_match, 0)
        elif result.returncode == 5:
            return CheckResult("backend pytest", "SKIP",
                               "No tests collected (exit 5)", 0)
        else:
            return CheckResult("backend pytest", "FAIL",
                               f"exit={result.returncode}: {last_lines[:200]}", 4)
    except subprocess.TimeoutExpired:
        return CheckResult("backend pytest", "FAIL",
                           "pytest timeout (>180s)", 4)
    except Exception as e:
        return CheckResult("backend pytest", "FAIL",
                           f"Error: {e}", 4)


# ─── Step 5: alembic upgrade head ────────────────────────────────────────────

def check_alembic(project_root: str) -> CheckResult:
    backend_dir = os.path.join(project_root, "backend")
    alembic_bin = os.path.join(backend_dir, ".venv", "bin", "alembic")
    alembic_bin = alembic_bin if (os.path.isfile(alembic_bin) and os.access(alembic_bin, os.X_OK)) \
                  else "alembic"

    try:
        # Non-destructive: check current vs heads (no upgrade)
        cur_result = subprocess.run(
            [alembic_bin, "current"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        heads_result = subprocess.run(
            [alembic_bin, "heads"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if cur_result.returncode != 0:
            return CheckResult("alembic upgrade head", "FAIL",
                               f"alembic current exit={cur_result.returncode}: {cur_result.stderr[:200]}", 5)
        if heads_result.returncode != 0:
            return CheckResult("alembic upgrade head", "FAIL",
                               f"alembic heads exit={heads_result.returncode}: {heads_result.stderr[:200]}", 5)

        cur_out = cur_result.stdout.strip()
        heads_out = heads_result.stdout.strip()

        # Parse head revision (take first line that looks like a revision hash)
        head_rev = None
        for line in heads_out.splitlines():
            m = re.match(r'^([0-9a-f]+)', line.strip())
            if m:
                head_rev = m.group(1)
                break

        # current output format: "0006_orders_aff_code (head)"
        cur_rev_match = re.match(r'^([0-9a-f]+)', cur_out.split()[0] if cur_out else "")
        cur_rev = cur_rev_match.group(1) if cur_rev_match else cur_out

        if cur_rev == head_rev:
            return CheckResult("alembic upgrade head", "PASS",
                               f"current={cur_rev} == head={head_rev}", 0)
        else:
            return CheckResult("alembic upgrade head", "FAIL",
                               f"current={cur_rev} != head={head_rev} (migrations pending)", 5)

    except subprocess.TimeoutExpired:
        return CheckResult("alembic upgrade head", "FAIL",
                           "alembic timeout (>30s)", 5)
    except Exception as e:
        return CheckResult("alembic upgrade head", "FAIL",
                           f"Error: {e}", 5)


# ─── Step 6: i18n no raw key ─────────────────────────────────────────────────
# Strategy: Check that all i18n keys referenced in .vue source files exist
# in the locale JSON files. This catches genuinely missing translations
# (typos, renamed keys, missing new keys) without false positives from
# vue-i18n's compiled key strings in the dist bundle.

I18N_KEY_ROOTS = [
    "home.", "auth.", "common.", "order.", "material.", "payment.",
    "nav.", "footer.", "profile.", "destinations.", "affiliate.",
    "checklist.", "materials.", "ocr.", "sms.", "error.",
]

# Regex to extract i18n key references from .vue source files
# Matches: t('key'), t("key"), $t('key'), i18n.t('key'), t(`key`), etc.
I18N_SOURCE_RE = re.compile(
    r'''(?<=[^\w])           # not preceded by word char
        (?:t|\$t|i18n\.t)\s* # translation function
        \(                   # opening paren
        \s*
        ([\x27\x22\x60])    # opening quote
        ((?:{roots})[\w.]*)  # the i18n key
        \1                   # matching closing quote
        '''.format(roots='|'.join(re.escape(k) for k in I18N_KEY_ROOTS)),
    re.VERBOSE
)


def check_i18n_raw_keys(project_root: str, frontend_dist: str) -> CheckResult:
    """
    Check that all i18n keys used in .vue source files exist in locale JSONs.
    Strategy:
    1. Load all locale JSON files (zh-CN, en, id-ID, vi-VN)
    2. Extract all i18n key references from .vue source files via t()/t("key")/t('key')
    3. For each referenced key, verify it exists in at least one locale file
    4. Report missing keys as FAIL
    """
    frontend_src = os.path.join(project_root, "frontend", "web", "src")
    shared_i18n = os.path.join(project_root, "frontend", "shared", "i18n")

    if not os.path.isdir(shared_i18n):
        return CheckResult("i18n no raw key", "SKIP",
                           f"Shared i18n dir not found: {shared_i18n}", 0)

    # Load all locale keys
    locale_files = ["zh-CN.json", "en.json", "id.json", "vi.json"]
    all_keys: set = set()
    for lf in locale_files:
        lf_path = os.path.join(shared_i18n, lf)
        if os.path.isfile(lf_path):
            try:
                import json
                data = json.loads(Path(lf_path).read_text(encoding="utf-8"))
                # Flatten nested dict to dot-separated keys
                def flatten(d, prefix=""):
                    for k, v in d.items():
                        if isinstance(v, dict):
                            flatten(v, prefix + k + ".")
                        else:
                            all_keys.add(prefix + k)
                flatten(data)
            except Exception:
                pass

    if not all_keys:
        return CheckResult("i18n no raw key", "SKIP",
                           "No locale keys loaded", 0)

    # Collect i18n keys used in .vue source files
    vue_dir = os.path.join(frontend_src, "views")
    if not os.path.isdir(vue_dir):
        return CheckResult("i18n no raw key", "SKIP",
                           f"Views dir not found: {vue_dir}", 0)

    used_keys: set = set()
    for vue_file in Path(vue_dir).rglob("*.vue"):
        try:
            content = vue_file.read_text(encoding="utf-8", errors="ignore")
            for m in I18N_SOURCE_RE.finditer(content):
                used_keys.add(m.group(2))  # group 2 = the key
        except Exception:
            pass

    # Check for missing keys
    missing = []
    for key in sorted(used_keys):
        if key not in all_keys:
            missing.append(key)

    if not missing:
        return CheckResult("i18n no raw key", "PASS",
                           f"All {len(used_keys)} keys exist in locale files", 0)
    else:
        return CheckResult("i18n no raw key", "FAIL",
                           f"{len(missing)} missing: {missing[:3]}", 6)


# ─── Step 7: .env / config.yaml readable ─────────────────────────────────────

def check_config_readable(project_root: str) -> CheckResult:
    backend_dir = os.path.join(project_root, "backend")
    issues = []
    ok = []

    # Check .env
    env_path = os.path.join(backend_dir, ".env")
    if os.path.isfile(env_path):
        if os.access(env_path, os.R_OK):
            ok.append(".env")
        else:
            issues.append(".env not readable")
    else:
        issues.append(".env not found")

    # Check config.yaml
    config_paths = [
        os.path.join(backend_dir, "config.yaml"),
        os.path.join(backend_dir, "app", "core", "config.py"),
    ]
    found_config = False
    for cp in config_paths:
        if os.path.isfile(cp) and os.access(cp, os.R_OK):
            ok.append(Path(cp).name)
            found_config = True
            break
    if not found_config:
        issues.append("config.yaml/config.py not found or not readable")

    if issues:
        return CheckResult(".env/config readable", "FAIL",
                           "; ".join(issues), 7)

    return CheckResult(".env/config readable", "PASS",
                       f"OK: {', '.join(ok)}", 0)


# ─── Main orchestration ───────────────────────────────────────────────────────

def run_verification(args: argparse.Namespace) -> VerifyReport:
    project_root = args.project_root or find_project_root()
    task_id = args.task_id

    # Auto-detect screenshots dir
    screenshots_dir = args.screenshots_dir
    if not screenshots_dir:
        for p in [f"outputs/{task_id}/screenshots",
                  "frontend/web/screenshots", "screenshots"]:
            if os.path.isdir(os.path.join(project_root, p)):
                screenshots_dir = p
                break

    # Auto-detect deliverable path
    deliverable_path = args.deliverable_path or f"outputs/{task_id}/deliverable.md"

    # Auto-detect WORKLOG path (plan workspace)
    worklog_path = args.worklog_path
    if not worklog_path:
        # Try plan workspace first, then backend root
        plan_worklog = os.path.join(project_root, "workspace", "backend", "WORKLOG.md")
        if os.path.isfile(plan_worklog):
            worklog_path = plan_worklog
        else:
            worklog_path = os.path.join(project_root, "workspace", "backend", "WORKLOG.md")

    report = VerifyReport(
        task_id=task_id,
        timestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        project_root=project_root,
    )

    steps = [
        ("Step 1", check_screenshots(screenshots_dir or "", project_root)),
        ("Step 2", check_deliverable(deliverable_path, project_root,
                                     min_bytes=args.min_bytes, min_lines=args.min_lines)),
        ("Step 3", check_worklog(worklog_path, task_id, project_root)),
        ("Step 4", check_pytest(args.pytest_target, project_root)),
        ("Step 5", check_alembic(project_root)),
        ("Step 6", check_i18n_raw_keys(project_root, args.frontend_dist)),
        ("Step 7", check_config_readable(project_root)),
    ]

    for label, result in steps:
        report.checks.append(result)
        if args.verbose:
            print(f"  [{label}] {result.name}: {result.result} — {result.detail}")

    fails = [c for c in report.checks if c.result == "FAIL"]
    if fails:
        report.overall = "FAIL"
        report.error_message = f"{fails[0].name}: {fails[0].detail}"

    return report


def main():
    parser = argparse.ArgumentParser(
        prog="d_verify_runner.py",
        description="D-VERIFY-RUNNER 1.0 — 7-Step Automated DoD Verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/d_verify_runner.py --task-id C-W11R-3 --verbose
  python tools/d_verify_runner.py --task-id C-W11R-3 --json
  python tools/d_verify_runner.py --task-id B-W7-1 --pytest-target tests/integration/test_orders.py
        """,
    )
    parser.add_argument("--task-id", required=True,
                        help="Task ID (e.g. C-W11R-3, B-W7-1)")
    parser.add_argument("--screenshots-dir",
                        help="Directory containing screenshots (auto-detected if omitted)")
    parser.add_argument("--deliverable-path",
                        help="Path to deliverable.md (default: outputs/<task-id>/deliverable.md)")
    parser.add_argument("--worklog-path",
                        help="Path to WORKLOG.md (default: workspace/backend/WORKLOG.md)")
    parser.add_argument("--pytest-target",
                        default="tests/integration/test_payment_stripe_stub.py",
                        help="Pytest target (default: tests/integration/test_payment_stripe_stub.py)")
    parser.add_argument("--project-root",
                        help="Project root (auto-detected if omitted)")
    parser.add_argument("--frontend-dist",
                        default="frontend/web/dist",
                        help="Frontend dist directory (default: frontend/web/dist)")
    parser.add_argument("--min-bytes", type=int, default=50,
                        help="Minimum deliverable size in bytes (default: 50)")
    parser.add_argument("--min-lines", type=int, default=10,
                        help="Minimum deliverable line count (default: 10)")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON format report")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")

    args = parser.parse_args()
    report = run_verification(args)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print(f"D-VERIFY-RUNNER 1.0 — TASK={report.task_id}")
        print(f"Project root: {report.project_root}")
        print(f"Time:        {report.timestamp}")
        print("=" * 60)
        for i, check in enumerate(report.checks, 1):
            status_icon = "✓" if check.result == "PASS" else ("⊘" if check.result == "SKIP" else "✗")
            print(f"  Step {i} [{status_icon} {check.result}] {check.name}")
            if check.detail:
                print(f"    → {check.detail}")
        print("-" * 60)
        overall_icon = "✓ PASS" if report.overall == "PASS" else "✗ FAIL"
        print(f"  Overall: {overall_icon}")
        if report.error_message:
            print(f"  Error: {report.error_message}")
        print("=" * 60)

    if report.overall == "FAIL":
        for i, check in enumerate(report.checks, 1):
            if check.result == "FAIL":
                sys.exit(check.exit_code if check.exit_code else i)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()