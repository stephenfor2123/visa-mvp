"""W8 end-to-end integration test — 4 subsystems (iOS + Minipgm + Insurance + Affiliate).

Scope (C-W8-5, plan_26a4c668):
  - test_ios_build           : flutter build ios --no-codesign --debug → BUILD SUCCEEDED
  - test_miniprogram_build   : npm run build:weapp → BUILD SUCCESS (62 files, 70 checks)
  - test_insurance_flow      : pytest test_insurance.py → 11 PASS
  - test_affiliate_flow      : pytest test_affiliate.py → 21 PASS

4 子系统全 PASS 才是 W8 gate PASS。

Reproducibility:
  集成测试脚本**不依赖外部服务** (不需 uvicorn / 真后端),纯 subprocess + 文件
  系统检查。`pytest -v` 可重复跑,iOS FAIL 不会 block 其他子系统。

环境依赖:
  - flutter (>= 3.44) on PATH
  - node (>= 18) on PATH for npm run build:weapp
  - .venv/bin/pytest (backend)
  - xcodebuild (可选,iOS build 依赖,本机 CommandLineTools 不够,会 FAIL — 环境硬伤)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import pytest

# --------------------------------------------------------------------------- #
# Paths                                                                       #
# --------------------------------------------------------------------------- #
WORKSPACE = Path("/Users/stephen/Desktop/签证项目")
IOS_DIR = WORKSPACE / "frontend" / "ios"
MP_DIR = WORKSPACE / "frontend" / "miniprogram"
BACKEND_DIR = WORKSPACE / "backend"
PYTEST_BIN = BACKEND_DIR / ".venv" / "bin" / "pytest"

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], cwd: Path | None, timeout: int = 600) -> Tuple[int, str, str]:
    """Run subprocess with timeout, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 127, "", f"command not found: {e}"


def _flutter_available() -> bool:
    return shutil.which("flutter") is not None


def _xcodebuild_full_install() -> bool:
    """True iff xcodebuild resolves (完整 Xcode, not CommandLineTools)."""
    rc, _, err = _run(["xcodebuild", "-version"], cwd=None, timeout=10)
    return rc == 0


# --------------------------------------------------------------------------- #
# Test 1: iOS build (flutter build ios --no-codesign --debug)                 #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestIosBuild:
    """iOS Flutter 工程 — A-W8-1 sub-task.

    DoD: flutter build ios --no-codesign --debug → BUILD SUCCEEDED.
    期望时长 5-10min,W8-1 plan 锁 30min timeout buffer。
    """

    def test_ios_dir_exists(self):
        """iOS Flutter 工程目录 + 关键文件存在性 (前置检查,不依赖 build)。"""
        assert IOS_DIR.is_dir(), f"iOS Flutter project missing: {IOS_DIR}"
        assert (IOS_DIR / "pubspec.yaml").is_file(), "pubspec.yaml missing"
        assert (IOS_DIR / "lib" / "main.dart").is_file(), "lib/main.dart missing"
        assert (IOS_DIR / "ios" / "Runner.xcodeproj").is_dir(), \
            "iOS native Runner.xcodeproj missing (nested at frontend/ios/ios/)"

    def test_ios_pages_count(self):
        """W8-1 要求 4 页 (login + home + register + materials)。"""
        pages_dir = IOS_DIR / "lib" / "pages"
        assert pages_dir.is_dir(), f"lib/pages missing: {pages_dir}"
        page_files = sorted(pages_dir.glob("*.dart"))
        assert len(page_files) >= 4, \
            f"expected ≥4 pages (login/home/register/materials), got {len(page_files)}: {[p.name for p in page_files]}"

    def test_ios_l10n_arb_count(self):
        """4 语种 ARB (en/zh/id/vi)。"""
        l10n_dir = IOS_DIR / "lib" / "l10n"
        if not l10n_dir.is_dir():
            pytest.skip("lib/l10n dir missing — flutter gen-l10n not configured")
        arb_files = sorted(l10n_dir.glob("app_*.arb"))
        assert len(arb_files) == 4, \
            f"expected 4 ARB files (en/zh/id/vi), got {len(arb_files)}: {[a.name for a in arb_files]}"

    @pytest.mark.skipif(not _flutter_available(), reason="flutter CLI not installed")
    def test_ios_flutter_pub_get(self):
        """flutter pub get → 依赖下载成功 (前置检查)。"""
        rc, out, err = _run(["flutter", "pub", "get"], cwd=IOS_DIR, timeout=300)
        assert rc == 0, f"flutter pub get FAIL (rc={rc}):\nSTDOUT: {out}\nSTDERR: {err}"

    @pytest.mark.skipif(not _flutter_available(), reason="flutter CLI not installed")
    def test_ios_flutter_analyze(self):
        """flutter analyze → 静态分析 0 error (DoD 不锁 warning)。"""
        rc, out, err = _run(["flutter", "analyze"], cwd=IOS_DIR, timeout=180)
        # 0 error 即过;warning 接受
        if rc != 0 and "No issues found" in (out + err):
            rc = 0  # flutter analyze exit 0/非 0 都可能,看 "No issues found" 才算
        if rc != 0 and "error" in (out + err).lower():
            pytest.fail(f"flutter analyze found errors:\n{out[-500:]}\n{err[-500:]}")

    @pytest.mark.skipif(not _flutter_available(), reason="flutter CLI not installed")
    def test_ios_flutter_test(self):
        """flutter test → widget_test.dart smoke test PASS。
        W8-1 修过 W6b 的 widget_test.dart L16 (MyApp → VisaIosApp),所以这个 test 必过。
        """
        rc, out, err = _run(["flutter", "test"], cwd=IOS_DIR, timeout=180)
        combined = out + err
        assert rc == 0, \
            f"flutter test FAIL (rc={rc}):\nSTDOUT: {out[-1000:]}\nSTDERR: {err[-1000:]}"
        assert "All tests passed" in combined or "+1" in combined, \
            f"flutter test exit 0 但 'All tests passed' 不在输出:\n{combined[-1000:]}"

    @pytest.mark.skipif(not _flutter_available(), reason="flutter CLI not installed")
    def test_ios_build(self):
        """核心 DoD: flutter build ios --no-codesign --debug → BUILD SUCCEEDED.
        期望 5-10min,W8-1 plan 锁 30min timeout。
        本机环境硬伤 (xcodebuild CommandLineTools 不够) 会 FAIL,但这是**环境问题
        不是 producer 代码 bug**。
        """
        rc, out, err = _run(
            ["flutter", "build", "ios", "--no-codesign", "--debug"],
            cwd=IOS_DIR,
            timeout=1800,  # 30 min
        )
        combined = out + err
        # Flutter 拒绝编译 (项目结构异常或 Xcode 缺失) 直接 fail
        assert rc == 0, \
            f"flutter build ios FAIL (rc={rc}).\n" \
            f"--- STDOUT (tail) ---\n{out[-2000:]}\n" \
            f"--- STDERR (tail) ---\n{err[-2000:]}"
        assert "Built " in combined or "BUILD SUCCESSFUL" in combined, \
            f"flutter build ios rc=0 但 'Built'/'BUILD SUCCESSFUL' 不在输出:\n{combined[-1500:]}"


# --------------------------------------------------------------------------- #
# Test 2: Minipgm build (npm run build:weapp)                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestMinipgmBuild:
    """微信小程序 build — A-W8-2 sub-task.

    DoD: npm run build:weapp → BUILD SUCCESS (62 files / 70 checks / 0 issues)。
    """

    def test_minipgm_dir_exists(self):
        assert MP_DIR.is_dir(), f"minipgm dir missing: {MP_DIR}"
        assert (MP_DIR / "package.json").is_file(), "package.json missing"
        assert (MP_DIR / "build_weapp.cjs").is_file(), "build_weapp.cjs missing"

    def test_minipgm_app_json_pages(self):
        """app.json 必含 ≥ 9 页 (5 W6b + 4 W8-2 新页)。"""
        app_json = MP_DIR / "app.json"
        assert app_json.is_file(), f"app.json missing: {app_json}"
        data = json.loads(app_json.read_text(encoding="utf-8"))
        pages = data.get("pages", [])
        assert len(pages) >= 9, \
            f"app.json expected ≥9 pages (5 W6b + 4 W8-2), got {len(pages)}: {pages}"

    def test_minipgm_pages_count(self):
        """pages/ 目录必含 ≥ 9 个 WXML (5 W6b + 4 W8-2)。"""
        pages_dir = MP_DIR / "pages"
        assert pages_dir.is_dir(), f"pages/ missing: {pages_dir}"
        wxmls = sorted(pages_dir.rglob("*.wxml"))
        assert len(wxmls) >= 9, \
            f"expected ≥9 .wxml files, got {len(wxmls)}: {[w.name for w in wxmls]}"

    def test_minipgm_i18n_count(self):
        """i18n 必含 4 语种 (zh-CN/en/id/vi)。"""
        i18n_dir = MP_DIR / "i18n"
        assert i18n_dir.is_dir(), f"i18n/ missing: {i18n_dir}"
        jsons = sorted(i18n_dir.glob("*.json"))
        assert len(jsons) >= 4, \
            f"expected ≥4 i18n json, got {len(jsons)}: {[j.name for j in jsons]}"

    def test_minipgm_screenshots_count_and_distinct(self):
        """截图 sha256 distinct (W6b 教训,producer 必须用真图不能用同图改 sha)。"""
        ss_dir = MP_DIR / "screenshots"
        assert ss_dir.is_dir(), f"screenshots/ missing: {ss_dir}"
        pngs = sorted(ss_dir.glob("*.png"))
        assert len(pngs) >= 4, \
            f"expected ≥4 W8-2 screenshots (order/payment/forgot/agreement), got {len(pngs)}"

        shas = set()
        for p in pngs:
            sha = subprocess.check_output(["shasum", "-a", "256", str(p)]).decode().split()[0]
            shas.add(sha)
        assert len(shas) == len(pngs), \
            f"截图 sha256 重复!{len(pngs)} 个文件只有 {len(shas)} 个 distinct sha (W6b 造假征兆)"

    def test_minipgm_build_weapp(self):
        """核心 DoD: npm run build:weapp → BUILD SUCCESS + 70 checks + 0 issues。"""
        rc, out, err = _run(
            ["npm", "run", "build:weapp"],
            cwd=MP_DIR,
            timeout=180,  # 3 min
        )
        combined = out + err
        assert rc == 0, \
            f"npm run build:weapp FAIL (rc={rc}):\nSTDOUT: {out[-1500:]}\nSTDERR: {err[-1500:]}"
        assert "BUILD_SUCCESS" in combined, \
            f"BUILD_SUCCESS marker missing:\n{combined[-1500:]}"
        assert "checks: 70" in combined and "issues: 0" in combined, \
            f"checks/issues 数字不对:\n{combined[-1500:]}"


# --------------------------------------------------------------------------- #
# Test 3: Insurance flow (pytest test_insurance.py)                           #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestInsuranceFlow:
    """拒签险接保 API — B-W8-3 sub-task.

    DoD: pytest test_insurance.py → 11 PASS,覆盖 factory / quote / bind / claim / JWT auth。
    """

    def test_pytest_available(self):
        assert PYTEST_BIN.is_file(), f"pytest not found at {PYTEST_BIN}"

    def test_insurance_service_file(self):
        """拒签险 service file 必存在 (B-W8-3 核心产出)。"""
        svc = BACKEND_DIR / "app" / "services" / "insurance_provider.py"
        assert svc.is_file(), f"insurance_provider.py missing: {svc}"

    def test_insurance_api_router(self):
        """拒签险 API router 必注册到 v2 (跟其它 v2 路由一致)。"""
        api = BACKEND_DIR / "app" / "api" / "v2" / "insurance.py"
        assert api.is_file(), f"insurance router missing: {api}"
        # 必含 4 端点
        text = api.read_text(encoding="utf-8")
        for ep in ("quote", "bind", "claim", "GET"):
            assert ep in text, f"insurance.py missing endpoint marker: {ep}"

    def test_insurance_pytest(self):
        """核心 DoD: pytest test_insurance.py → 11 PASS。"""
        rc, out, err = _run(
            [str(PYTEST_BIN), "tests/integration/test_insurance.py", "-v"],
            cwd=BACKEND_DIR,
            timeout=120,
        )
        combined = out + err
        assert rc == 0, \
            f"pytest test_insurance.py FAIL (rc={rc}):\n{combined[-2000:]}"
        assert "11 passed" in combined, \
            f"expected '11 passed', got:\n{combined[-1500:]}"


# --------------------------------------------------------------------------- #
# Test 4: Affiliate flow (pytest test_affiliate.py)                           #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestAffiliateFlow:
    """Affiliate 系统 — B-W8-4 sub-task.

    DoD: pytest test_affiliate.py → 21 PASS,覆盖 factory / track / commission / payout / partner stats。
    """

    def test_affiliate_service_file(self):
        """Affiliate service file 必存在 (B-W8-4 核心产出)。"""
        svc = BACKEND_DIR / "app" / "services" / "affiliate_provider.py"
        assert svc.is_file(), f"affiliate_provider.py missing: {svc}"

    def test_affiliate_api_router(self):
        """Affiliate API router 必注册到 v2。"""
        api = BACKEND_DIR / "app" / "api" / "v2" / "affiliate.py"
        assert api.is_file(), f"affiliate router missing: {api}"

    def test_affiliate_no_real_credentials(self):
        """零凭据:无 AFFILIATE_* env var (跟 W8-3 一致,纯 Mock)。"""
        # 扫 .env 文件和 settings
        env_file = BACKEND_DIR / ".env"
        if env_file.is_file():
            text = env_file.read_text(encoding="utf-8")
            for k in ("AFFILIATE_API_KEY", "AFFILIATE_BASE_URL", "AFFILIATE_PARTNER_KEY"):
                assert k not in text, \
                    f"Affiliate 真凭据 {k} 出现在 .env — B-W8-4 应当全 Mock!"

    def test_affiliate_pytest(self):
        """核心 DoD: pytest test_affiliate.py → 21 PASS。"""
        rc, out, err = _run(
            [str(PYTEST_BIN), "tests/integration/test_affiliate.py", "-v"],
            cwd=BACKEND_DIR,
            timeout=120,
        )
        combined = out + err
        assert rc == 0, \
            f"pytest test_affiliate.py FAIL (rc={rc}):\n{combined[-2000:]}"
        assert "21 passed" in combined, \
            f"expected '21 passed', got:\n{combined[-1500:]}"


# --------------------------------------------------------------------------- #
# Test 5: 跨子系统 端到端 smoke (wire-level 4 子系统收口)                       #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestCrossSubsystem:
    """W8 gate 收口 — 4 子系统联动 sanity check。
    
    这一组 test 不重复任何子系统 test,而是验证 W8 整体验收:
      - 4 子系统产物文件都存在 (front-end + back-end 都有交付)
      - 4 子系统 deliverable.md 都存在
      - A_WORKLOG.md / C_WORKLOG.md / backend/WORKLOG.md 都有 W8-* 行
    """

    def test_4_subsystem_files_present(self):
        """4 子系统核心文件存在 (sanity check)。"""
        files = [
            # A-W8-1 iOS
            IOS_DIR / "lib" / "pages" / "home_page.dart",
            IOS_DIR / "lib" / "pages" / "register_page.dart",
            IOS_DIR / "lib" / "pages" / "materials_page.dart",
            # A-W8-2 minipgm
            MP_DIR / "pages" / "order" / "order.wxml",
            MP_DIR / "pages" / "payment" / "payment.wxml",
            MP_DIR / "pages" / "forgot" / "forgot.wxml",
            MP_DIR / "pages" / "agreement" / "agreement.wxml",
            # B-W8-3 insurance
            BACKEND_DIR / "app" / "services" / "insurance_provider.py",
            BACKEND_DIR / "app" / "api" / "v2" / "insurance.py",
            # B-W8-4 affiliate
            BACKEND_DIR / "app" / "services" / "affiliate_provider.py",
            BACKEND_DIR / "app" / "api" / "v2" / "affiliate.py",
        ]
        missing = [str(f) for f in files if not f.is_file()]
        assert not missing, f"W8 4 子系统核心文件缺失:\n  " + "\n  ".join(missing)

    def test_4_subsystem_deliverables_present(self):
        """4 子系统 deliverable.md 都存在 (W8-1 必查 brief 约束 #2)。"""
        plan_outputs = Path("/Users/stephen/.mavis/plans/plan_26a4c668/outputs")
        expected = {
            "A-W8-1": plan_outputs / "A-W8-1" / "deliverable.md",
            "A-W8-2": plan_outputs / "A-W8-2" / "deliverable.md",
            "B-W8-3": plan_outputs / "B-W8-3" / "deliverable.md",
            "B-W8-4": plan_outputs / "B-W8-4" / "deliverable.md",
        }
        for sub, path in expected.items():
            if not path.is_file():
                pytest.fail(
                    f"{sub} deliverable.md 缺失: {path}\n"
                    f"  → W8 gate FAIL,producer 必须补"
                )

    def test_worklogs_have_w8_markers(self):
        """3 个 WORKLOG 都必含 W8-* 收口行 (W8-1/2/3/4/5)。"""
        checks = [
            ("A_WORKLOG", WORKSPACE / "A_WORKLOG.md", ["W8-2"]),
            ("C_WORKLOG", WORKSPACE / "C_WORKLOG.md", ["W8-5"]),
            ("backend_WORKLOG", BACKEND_DIR / "WORKLOG.md", ["W8-3", "W8-4"]),
        ]
        for name, path, markers in checks:
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            for m in markers:
                assert m in text, \
                    f"{name} ({path}) 缺 marker '{m}' — W8 收口行必写"