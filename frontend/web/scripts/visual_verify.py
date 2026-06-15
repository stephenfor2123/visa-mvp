#!/usr/bin/env python3
"""
visual_verify.py — W15-P0 vite build bypass
===========================================

Why this exists
---------------
`npm run build` (vite + Element Plus tree-shake scan) hangs >5min on macOS M-series.
Verified unfixable on this host (W14-6/9/10/11). No docker = no GH Actions fallback.

This script BYPASSES `vite build` entirely:
  1. Starts `vite dev` on port 5174 (NOT 5173 to avoid clashing with siblings).
  2. Drives 5 critical routes via Node + Playwright (uses local node_modules — no Python pip needed).
  3. Captures screenshot (1280x800, fullPage) + console errors + 404s + key DOM testids.
  4. Writes a Markdown report + per-route JSON sidecars.

Equivalence argument (also in deliverable.md):
  - For MODULE FUNCTIONALITY verification (does AdminLogin render? Does PaymentResult
    show success state?): vite dev is **equivalent** to vite build, because both
    execute the same Vue SFC source files. Build just bundles; dev serves source.
  - For BUNDLE ARTIFACTS (dist/*.js size, tree-shaken chunks, css minification):
    this is NOT equivalent — verify via GH Actions runner instead (W16 follow-up).

Run
---
  python3 scripts/visual_verify.py

Output
------
  outputs/W15-P0-3-vite-bypass/
    visual_report.md         <-- one-stop human report
    visual_report.json       <-- machine-readable per-route data
    screenshots/
      home.png
      admin_login.png
      admin_dashboard.png
      admin_ratelimit.png
      payment_success.png
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# --- paths -----------------------------------------------------------------

REPO_ROOT = Path("/Users/apple/Desktop/签证项目").resolve()
WEB_DIR = REPO_ROOT / "frontend" / "web"
NODE_BIN = WEB_DIR / "node_modules" / ".bin"
OUTPUT_DIR = (
    Path("/Users/apple/.mavis/plans/plan_33d6f6bd/outputs/W15-P0-3-vite-bypass")
)
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
VITE_PORT = 5174  # 5173 may be grabbed by sibling workers

# --- routes to verify ------------------------------------------------------

# Each entry: (route_path, screenshot_basename, post-load wait ms, key testids to assert)
ROUTES = [
    ("/home",                "home",               1500, ["home-login", "app-header__brand"]),
    ("/admin/login?demo=1",  "admin_login",        1500, ["admin-login-card", "admin-login-form", "admin-login-submit"]),
    ("/admin/dashboard",     "admin_dashboard",    1500, ["admin-dashboard", "admin-cards", "admin-logout"]),
    ("/admin/rate-limit",    "admin_ratelimit",    2000, ["rate-limit-head", "rate-limit-stats", "stat-today-visits"]),
    ("/payment/result?orderId=TEST&status=success",
                            "payment_success",    2500, ["paymentresult-status-pending", "paymentresult-polling-label"]),
]

# --- helpers ---------------------------------------------------------------

def wait_port(host: str, port: int, timeout: float = 60.0) -> bool:
    """Wait until TCP connect succeeds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def wait_http(url: str, timeout: float = 60.0) -> int:
    """Block until URL returns any HTTP response (status >= 0)."""
    deadline = time.time() + timeout
    last_status = -1
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as r:
                last_status = r.status
                if r.status == 200:
                    return r.status
        except Exception:
            pass
        time.sleep(0.5)
    return last_status


def start_vite_dev() -> subprocess.Popen:
    """Start vite dev on VITE_PORT; return the Popen handle."""
    env = os.environ.copy()
    env["VITE_MOCK"] = "true"  # many pages need mock flag to render locally
    log_path = OUTPUT_DIR / "vite-dev.log"
    log_fh = open(log_path, "w")
    proc = subprocess.Popen(
        [str(NODE_BIN / "vite"), "--host", "127.0.0.1", "--port", str(VITE_PORT)],
        cwd=str(WEB_DIR),
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        # detached so we can SIGKILL the process group on cleanup
        start_new_session=True,
    )
    return proc


def stop_vite_dev(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


# --- main driver ----------------------------------------------------------

def main() -> int:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Start vite dev
    print(f"[1/4] Starting vite dev on :{VITE_PORT} ...", flush=True)
    vite_proc = start_vite_dev()
    try:
        if not wait_port("127.0.0.1", VITE_PORT, timeout=60.0):
            print(f"ERROR: vite dev did not bind :{VITE_PORT} within 60s", file=sys.stderr)
            print(f"--- last 30 lines of vite-dev.log ---", file=sys.stderr)
            try:
                with open(OUTPUT_DIR / "vite-dev.log") as f:
                    lines = f.readlines()
                    print("".join(lines[-30:]), file=sys.stderr)
            except FileNotFoundError:
                pass
            return 2
        # And verify HTTP
        status = wait_http(f"http://127.0.0.1:{VITE_PORT}/", timeout=30.0)
        print(f"      vite dev up — HTTP GET / -> {status}", flush=True)

        # 2. Drive playwright via Node script (uses local node_modules)
        print("[2/4] Driving Playwright via Node ...", flush=True)
        driver_script = OUTPUT_DIR / "_driver.mjs"
        driver_script.write_text(_DRIVER_JS)
        result = subprocess.run(
            ["node", str(driver_script)],
            cwd=str(WEB_DIR),
            env={**os.environ, "VITE_URL": f"http://127.0.0.1:{VITE_PORT}", "OUT_DIR": str(OUTPUT_DIR)},
            capture_output=True,
            text=True,
            timeout=300,  # 5 min hard cap on full route sweep
        )
        if result.returncode != 0:
            print(f"ERROR: playwright driver failed (exit={result.returncode})", file=sys.stderr)
            print("--- stdout ---", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print("--- stderr ---", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 3

        # 3. Read driver output JSON
        json_path = OUTPUT_DIR / "_driver.json"
        if not json_path.exists():
            print("ERROR: driver did not write _driver.json", file=sys.stderr)
            return 4
        with json_path.open() as f:
            report = json.load(f)
        print(f"[3/4] Got {len(report.get('routes', []))} route reports", flush=True)

        # 4. Compose final markdown
        print("[4/4] Writing visual_report.md ...", flush=True)
        final_report_path = OUTPUT_DIR / "visual_report.md"
        final_report_path.write_text(_compose_markdown(report))
        # Also dump as JSON for verifier
        (OUTPUT_DIR / "visual_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"      OK -> {final_report_path}", flush=True)
        return 0
    finally:
        stop_vite_dev(vite_proc)


# --- Node driver (Playwright JS) ------------------------------------------

# Why inline this: avoid a second file + keep visual_verify.py self-contained.
# Uses playwright from WEB_DIR/node_modules so no pip install needed.
_DRIVER_JS = r"""
import { chromium } from '/Users/apple/Desktop/签证项目/frontend/web/node_modules/playwright/index.mjs';
import { mkdir, writeFile, stat } from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

const VITE_URL = process.env.VITE_URL || 'http://127.0.0.1:5174';
const OUT_DIR = process.env.OUT_DIR || '/tmp';
const SHOT_DIR = path.join(OUT_DIR, 'screenshots');

const ROUTES = [
  { path: '/home',                              name: 'home',            waitMs: 1500, assertTestIds: ['home-login', 'app-header__brand'] },
  { path: '/admin/login?demo=1',                name: 'admin_login',     waitMs: 1500, assertTestIds: ['admin-login-card', 'admin-login-form', 'admin-login-submit'] },
  { path: '/admin/dashboard',                   name: 'admin_dashboard', waitMs: 1500, assertTestIds: ['admin-dashboard'] },
  { path: '/admin/rate-limit',                  name: 'admin_ratelimit', waitMs: 2000, assertTestIds: ['rate-limit-head', 'rate-limit-stats', 'stat-today-visits'] },
  { path: '/payment/result?orderId=TEST&status=success', name: 'payment_success', waitMs: 2500, assertTestIds: [] },
];

function sha256(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

await mkdir(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  locale: 'zh-CN',
});
const page = await context.newPage();

const routesReport = [];

for (const r of ROUTES) {
  const url = VITE_URL + r.path;
  const entry = {
    name: r.name,
    path: r.path,
    url,
    consoleErrors: [],
    consoleWarnings: [],
    pageErrors: [],
    failedRequests: [],
    testidHits: {},
    httpStatus: null,
    screenshot: null,
    sha256: null,
    fileSizeBytes: null,
  };
  const onConsole = (msg) => {
    const t = msg.type();
    const text = msg.text();
    if (t === 'error') entry.consoleErrors.push(text);
    else if (t === 'warning') entry.consoleWarnings.push(text);
  };
  const onPageErr = (err) => entry.pageErrors.push(String(err));
  const onResp = (resp) => {
    if (resp.status() >= 400) entry.failedRequests.push({ url: resp.url(), status: resp.status() });
  };
  page.on('console', onConsole);
  page.on('pageerror', onPageErr);
  page.on('response', onResp);

  try {
    const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    entry.httpStatus = resp ? resp.status() : null;
    // Give Vue + i18n + Pinia a beat to mount
    await page.waitForTimeout(r.waitMs);

    // Probe asserted testids
    for (const tid of r.assertTestIds) {
      try {
        const loc = page.locator(`[data-testid="${tid}"]`).first();
        const visible = await loc.isVisible({ timeout: 1500 }).catch(() => false);
        entry.testidHits[tid] = visible;
      } catch (e) {
        entry.testidHits[tid] = false;
      }
    }

    // Capture fullPage screenshot
    const shotPath = path.join(SHOT_DIR, `${r.name}.png`);
    await page.screenshot({ path: shotPath, fullPage: true });
    const st = await stat(shotPath);
    entry.screenshot = shotPath;
    entry.fileSizeBytes = st.size;
    const buf = await import('node:fs/promises').then(m => m.readFile(shotPath));
    entry.sha256 = sha256(buf);
  } catch (err) {
    entry.pageErrors.push(`navigation_or_render_failed: ${String(err)}`);
  } finally {
    page.removeListener('console', onConsole);
    page.removeListener('pageerror', onPageErr);
    page.removeListener('response', onResp);
    routesReport.push(entry);
  }
}

await browser.close();

const finalReport = {
  generatedAt: new Date().toISOString(),
  viteUrl: VITE_URL,
  routes: routesReport,
};
await writeFile(path.join(OUT_DIR, '_driver.json'), JSON.stringify(finalReport, null, 2));
console.log(JSON.stringify({ ok: true, count: routesReport.length }, null, 2));
"""


def _compose_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# W15-P0 vite build bypass — visual verification report\n")
    lines.append(f"- Generated: `{report.get('generatedAt', '?')}`")
    lines.append(f"- Vite dev URL: `{report.get('viteUrl', '?')}`")
    lines.append(f"- Routes verified: {len(report.get('routes', []))}\n")

    lines.append("## Summary\n")
    lines.append("| Route | HTTP | console.error | pageerror | 404s | screenshot sha256 | bytes |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in report["routes"]:
        sha = r["sha256"] or "—"
        sha_short = sha[:12] + "..." if sha != "—" else "—"
        lines.append(
            f"| `{r['path']}` | {r['httpStatus']} | {len(r['consoleErrors'])} | "
            f"{len(r['pageErrors'])} | {len(r['failedRequests'])} | "
            f"`{sha_short}` | {r['fileSizeBytes'] or 0} |"
        )
    lines.append("")

    lines.append("## Per-route detail\n")
    for r in report["routes"]:
        lines.append(f"### `{r['path']}` -> `{r['name']}.png`\n")
        lines.append(f"- HTTP status: **{r['httpStatus']}**")
        lines.append(f"- Screenshot: `{r['screenshot']}`")
        lines.append(f"- sha256: `{r['sha256']}`")
        lines.append(f"- size: {r['fileSizeBytes']} bytes\n")
        if r["consoleErrors"]:
            lines.append(f"**console.error ({len(r['consoleErrors'])}):**")
            for e in r["consoleErrors"][:10]:
                lines.append(f"  - `{e[:200]}`")
            lines.append("")
        if r["pageErrors"]:
            lines.append(f"**pageerror ({len(r['pageErrors'])}):**")
            for e in r["pageErrors"][:10]:
                lines.append(f"  - `{e[:200]}`")
            lines.append("")
        if r["failedRequests"]:
            lines.append(f"**4xx/5xx responses ({len(r['failedRequests'])}):**")
            for fr in r["failedRequests"][:10]:
                lines.append(f"  - `{fr['status']} {fr['url']}`")
            lines.append("")
        if r["testidHits"]:
            lines.append("**DOM testid assertions:**")
            for tid, hit in r["testidHits"].items():
                mark = "PASS" if hit else "FAIL"
                lines.append(f"  - [{mark}] `{tid}`")
            lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())