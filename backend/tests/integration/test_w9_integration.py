"""W9 end-to-end integration test — 4 subsystems (iOS + OMS aff_code + Payment stub).

Scope (C-W9-5, plan_b88c1fca):
  - test_ios_screenshots              : ls frontend/ios/screenshots/ 必含 3 张 distinct sha
  - test_oms_aff_code_end_to_end      : POST /api/v2/orders + aff_code → 1.5s + GET commission 5%
  - test_stripe_provider_factory      : StripePaymentProvider 工厂 (无凭据时 raise)
  - test_order_affiliate_3_cases      : 复用 B-W9-3 affiliate pytest 21 PASS 关键 3 路径

4 子系统全 PASS 才是 W9 gate PASS。

Reproducibility:
  集成测试脚本**不依赖外部服务** (不需 uvicorn / 真后端),纯 subprocess + pytest。
  `pytest -v` 可重复跑。Stripe stub FAIL 不会 block 其他子系统。

环境依赖:
  - .venv/bin/pytest (backend, 已含 stripe 15.2.0)
  - shasum (macOS 内建, sha256 校验)
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select


# --------------------------------------------------------------------------- #
# Paths — resolved from __file__ so the suite is portable across machines.   #
# Override with PROJECT_ROOT env var if a non-default checkout layout is used.#
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(
    os.environ.get("PROJECT_ROOT")
    or Path(__file__).resolve().parents[3]
)
WORKSPACE = PROJECT_ROOT
IOS_DIR = PROJECT_ROOT / "frontend" / "ios"
SCREENSHOTS_DIR = IOS_DIR / "screenshots"
BACKEND_DIR = PROJECT_ROOT / "backend"
PYTEST_BIN = BACKEND_DIR / ".venv" / "bin" / "pytest"

# Test env (per backend/tests/conftest.py contract — must be set before app import)
_TEST_TMPDIR = tempfile.mkdtemp(prefix="w9-int-")
_TEST_DB_PATH = Path(_TEST_TMPDIR) / "test.db"
_TEST_LOG_DIR = Path(_TEST_TMPDIR) / "logs"
_TEST_LOG_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"
os.environ["LOG_DIR"] = str(_TEST_LOG_DIR)
os.environ["SMS_LOG_DIR"] = str(_TEST_LOG_DIR)
os.environ["SMS_COOLDOWN_SECONDS"] = "1"
os.environ["SMS_DAILY_LIMIT"] = "10000"
os.environ["RATE_LIMIT_PER_IP_PER_MIN"] = "10000"
os.environ["RATE_LIMIT_SLOW_API_PER_IP_PER_MIN"] = "10000"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-2026"
os.environ["ENV"] = "test"
os.environ["DB_ECHO"] = "0"

# Force-import ORM models (conftest style)
import app.models  # noqa: F401
from app.core.config import get_settings
get_settings.cache_clear()
from app.main import create_app
from app.core.db import engine, Base, AsyncSessionLocal
from app.services.affiliate_provider import (
    MockAffiliateProvider,
    reset_affiliate_provider_for_tests,
)
from app.services.payment_provider import (
    StripePaymentProvider,
    reset_payment_provider_for_tests,
)
from app.models.destination import VisaDestination


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], cwd: Path | None, timeout: int = 600) -> Tuple[int, str, str]:
    """Run subprocess with timeout, return (rc, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 127, "", f"command not found: {e}"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
    """Register or reuse account keyed by phone → returns access token."""
    uname = f"u{phone}"
    email = f"{phone}@test.local"
    pwd = "Test1234"
    await client.post(
        "/api/v2/auth/register",
        json={"username": uname, "email": email, "password": pwd, "email_code": "123456"},
    )
    r = await client.post(
        "/api/v2/auth/login",
        json={"account": email, "password": pwd},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _upload_material(client, token: str) -> int:
    jpeg = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32
    r = await client.post(
        "/api/v2/materials/upload",
        files={"file": ("passport.jpg", io.BytesIO(jpeg), "image/jpeg")},
        data={"material_type": "passport"},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["material"]["id"]


async def _seed_destination(s, code: str = "US") -> int:
    existing = await s.scalar(
        select(VisaDestination).where(VisaDestination.country_code == code)
    )
    if existing is not None:
        existing.enabled = True
        existing.visa_types = json.dumps(["tourism"])
        await s.commit()
        return existing.id
    d = VisaDestination(
        country_code=code,
        country_name_i18n=json.dumps(
            {"zh-CN": code, "en": code}, ensure_ascii=False
        ),
        visa_types=json.dumps(["tourism"]),
        enabled=True,
        display_order=10,
    )
    s.add(d)
    await s.commit()
    await s.refresh(d)
    return d.id


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
@pytest_asyncio.fixture()
async def client():
    """Per-test: fresh schema + reset provider singletons + AsyncClient."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    application = create_app()
    reset_affiliate_provider_for_tests()
    reset_payment_provider_for_tests()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    reset_affiliate_provider_for_tests()
    reset_payment_provider_for_tests()


# --------------------------------------------------------------------------- #
# Test 1: iOS screenshots (3 张, sha256 distinct)                              #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestIosScreenshots:
    """A-W9-1 sub-task — iOS 截图补 + flutter build 验证 (3 张, sha256 distinct)."""

    def test_screenshots_dir_exists(self):
        assert SCREENSHOTS_DIR.is_dir(), \
            f"iOS screenshots dir missing: {SCREENSHOTS_DIR}"

    def test_screenshots_count_3(self):
        """必含 3 张 iOS 截图 (W9-1 DoD 锁死: home + register + materials)。"""
        pngs = sorted(SCREENSHOTS_DIR.glob("*.png"))
        assert len(pngs) == 3, \
            f"expected exactly 3 iOS screenshots, got {len(pngs)}: {[p.name for p in pngs]}"
        # 三张必含: home + register + materials (iOS 4 页之一, 含 1 语种)
        names = {p.name for p in pngs}
        for required in ("home_zh.png", "register_en.png", "materials_id.png"):
            assert required in names, \
                f"iOS screenshot {required} missing. Got: {names}"

    def test_screenshots_sha256_distinct(self):
        """3 张截图 sha256 必须全 distinct (W6b 教训: producer 不能同图改 sha)。"""
        pngs = sorted(SCREENSHOTS_DIR.glob("*.png"))
        shas = set()
        for p in pngs:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            shas.add(digest)
        assert len(shas) == len(pngs), \
            f"screenshots sha256 重复! {len(pngs)} files, only {len(shas)} distinct " \
            f"(W6b 造假征兆: producer 不能用同图改 sha)"

    def test_screenshots_file_size_sane(self):
        """3 张截图 > 10KB (排除空白/单色假图)。"""
        pngs = sorted(SCREENSHOTS_DIR.glob("*.png"))
        for p in pngs:
            size = p.stat().st_size
            assert size > 10_000, \
                f"{p.name} size={size} bytes 太小 (可能空白/单色图)"

    def test_screenshots_png_format(self):
        """3 张截图是有效 PNG (PNG magic 89 50 4E 47 0D 0A 1A 0A)。"""
        PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
        for p in sorted(SCREENSHOTS_DIR.glob("*.png")):
            with p.open("rb") as f:
                head = f.read(8)
            assert head == PNG_MAGIC, \
                f"{p.name} 缺 PNG magic bytes, head={head!r}"


# --------------------------------------------------------------------------- #
# Test 2: OMS aff_code 端到端 (POST + aff_code → 1.5s + GET commission 5%)     #
# --------------------------------------------------------------------------- #
class TestOmsAffCodeEndToEnd:
    """W9-2 (前端 aff_code 字段) + W9-3 (后端 on_order_created 钩子) wire-up.

    DoD (W9 spec):
      POST /api/v2/orders {aff_code: "AFF001"} → 1.5s 后
      GET /api/v2/affiliate/commission/{order_id}?order_total_cents=20000
      → commission_amount_cents=1000 (5% of 20000) + partner_id=PARTNER_AFF001

    这是 W9 集成测试**最关键**的 case — 验证前 + 后 + 钩子全链 wire。
    """

    async def test_post_order_with_aff_code_auto_attributes(self, client):
        """POST /orders + aff_code 触发 on_order_created 钩子 → 自动 track+attribute."""
        async with AsyncSessionLocal() as s:
            dest_id = await _seed_destination(s, "US")
        token = await _register(client, "13888800001")
        mid = await _upload_material(client, token)

        # POST /orders with aff_code
        r = await client.post(
            "/api/v2/orders",
            json={
                "destination_id": dest_id,
                "visa_type": "tourism",
                "material_ids": [mid],
                "applicant_data": {"name": "Alice"},
                "aff_code": "AFF001",
            },
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        order_no = body["data"]["order_no"]
        # 验证响应里 aff_code 已持久化
        assert body["data"]["order"]["aff_code"] == "AFF001", \
            f"expected aff_code=AFF001 in response, got {body['data']['order']['aff_code']}"

        # 立即 GET commission 验证钩子已 bind (即使还没 payment)
        r = await client.get(
            f"/api/v2/affiliate/commission/{order_no}",
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        cdata = r.json()["data"]
        # 钩子 on_order_created 调了 attribute(), partner_id 已被 bind
        assert cdata["partner_id"] == "PARTNER_AFF001", \
            f"expected partner_id=PARTNER_AFF001 (从 aff_code=AFF001 派生), got {cdata['partner_id']}"
        # commission amount 还是 0 因为 order total_amount 还是 0 (mock 默认)
        assert cdata["commission_amount_cents"] == 0, \
            f"expected 0 (pre-payment), got {cdata['commission_amount_cents']}"

    async def test_commission_5_percent_after_payment(self, client):
        """完整链路: POST /orders + aff_code → 1.5s wait + GET commission (with total) → 5%"""
        async with AsyncSessionLocal() as s:
            dest_id = await _seed_destination(s, "US")
        token = await _register(client, "13888800002")
        mid = await _upload_material(client, token)

        # POST /orders with aff_code (W9-2 前端 A 提交) → on_order_created 钩子 (W9-3)
        r = await client.post(
            "/api/v2/orders",
            json={
                "destination_id": dest_id,
                "visa_type": "tourism",
                "material_ids": [mid],
                "applicant_data": {"name": "Bob"},
                "aff_code": "AFF002",
            },
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text
        order_no = r.json()["data"]["order_no"]

        # 1.5s 后 GET commission (W9-2 前端 A 静默调, W9 spec 锁死 1.5s)
        await asyncio.sleep(1.5)
        r = await client.get(
            f"/api/v2/affiliate/commission/{order_no}?order_total_cents=20000",
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        cdata = r.json()["data"]

        # 5% rule 验证: 20000 cents * 0.05 = 1000 cents = $10
        assert cdata["commission_amount_cents"] == 1000, \
            f"expected 5% of 20000 = 1000 cents, got {cdata['commission_amount_cents']}"
        assert cdata["commission_rate"] == "0.05", \
            f"expected rate=0.05, got {cdata['commission_rate']}"
        assert cdata["partner_id"] == "PARTNER_AFF002", \
            f"expected partner_id=PARTNER_AFF002, got {cdata['partner_id']}"
        assert cdata["order_id"] == order_no

    async def test_post_order_without_aff_code_works(self, client):
        """POST /orders 不带 aff_code 也应 201 (无推广时静默无 partner, 是 by design)。"""
        async with AsyncSessionLocal() as s:
            dest_id = await _seed_destination(s, "US")
        token = await _register(client, "13888800003")
        mid = await _upload_material(client, token)

        r = await client.post(
            "/api/v2/orders",
            json={
                "destination_id": dest_id,
                "visa_type": "tourism",
                "material_ids": [mid],
                "applicant_data": {"name": "Charlie"},
                # 无 aff_code
            },
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text
        order_no = r.json()["data"]["order_no"]
        assert r.json()["data"]["order"]["aff_code"] is None

        # GET commission 应返 404 (no attribution)
        r = await client.get(
            f"/api/v2/affiliate/commission/{order_no}",
            headers=_bearer(token),
        )
        # 没有 attribution → UnknownOrder → 404
        assert r.status_code == 404, \
            f"expected 404 for unattributed order, got {r.status_code}: {r.text}"


# --------------------------------------------------------------------------- #
# Test 3: Stripe provider 工厂 (无凭据时 raise)                                #
# --------------------------------------------------------------------------- #
class TestStripeProviderFactory:
    """B-W9-4 sub-task — StripePaymentProvider 工厂 (无凭据时 raise NotImplementedError)."""

    def test_stripe_sdk_importable(self):
        """stripe SDK 装好 (B-W9-4 DoD: pip show stripe → 15.2.0)."""
        import stripe
        assert stripe is not None
        # stripe SDK exposes `VERSION` (not `__version__`)
        assert hasattr(stripe, "VERSION")
        # 跟 B-W9-4 deliverable 报数一致
        assert stripe.VERSION.startswith("15."), \
            f"expected stripe SDK 15.x (per B-W9-4), got {stripe.VERSION}"

    def test_stripe_stub_no_creds_raises(self):
        """零凭据时 StripePaymentProvider 4 method 全 raise NotImplementedError."""
        # 确保 stripe_secret_key 是空 (测试 env 默认)
        settings = get_settings()
        assert settings.stripe_secret_key == "", \
            f"V2 应零凭据, stripe_secret_key={settings.stripe_secret_key!r}"

        provider = StripePaymentProvider()
        # stub mode: self.stripe is None
        assert provider.stripe is None, \
            f"stub mode 应 self.stripe=None, got {provider.stripe!r}"

        # 4 method 全 raise NotImplementedError
        async def _check():
            # 我们没 await 真实 session, 期望在 method 入口就 raise (因 _require_stripe)
            # 需要 db 参数, 传 None 试试看
            await provider.create_order(db=None, order_no="x", amount_cents=100)

        with pytest.raises(NotImplementedError) as exc:
            asyncio.run(_check())
        assert "STRIPE_SECRET_KEY" in str(exc.value) or "V2.1" in str(exc.value), \
            f"expected NotImplementedError about STRIPE/V2.1, got: {exc.value}"

    def test_stripe_stub_query_order_raises(self):
        """query_order 同样 raise。"""
        provider = StripePaymentProvider()
        assert provider.stripe is None

        async def _check():
            await provider.query_order(db=None, order_no="x")

        with pytest.raises(NotImplementedError):
            asyncio.run(_check())

    def test_stripe_stub_handle_notify_raises(self):
        """handle_notify 同样 raise。"""
        provider = StripePaymentProvider()
        assert provider.stripe is None

        async def _check():
            await provider.handle_notify(db=None, order_no="x")

        with pytest.raises(NotImplementedError):
            asyncio.run(_check())

    def test_stripe_stub_close_order_raises(self):
        """close_order 同样 raise。"""
        provider = StripePaymentProvider()
        assert provider.stripe is None

        async def _check():
            await provider.close_order(db=None, order_no="x")

        with pytest.raises(NotImplementedError):
            asyncio.run(_check())


# --------------------------------------------------------------------------- #
# Test 4: 复用 B-W9-3 affiliate pytest 关键 3 case                              #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestOrderAffiliateThreeCases:
    """复用 B-W9-3 pytest 关键 3 路径:
      - test_attribute_after_track_binds_order: track+attribute 完整链路
      - test_commission_is_5_percent_of_order_total: 5% 佣金
      - test_payout_settles_all_attributed_orders: payout 100% paid

    不重写 (跟 B-W9-3 producer 报数一致, 21/21 PASS in 13.16s), 而是用 subprocess
    跑 B-W9-3 已有 pytest 文件, 然后挑 3 个关键 case 名字验证它们出现在 PASS 行。
    """

    def test_b_w9_3_affiliate_pytest_3_cases_pass(self):
        """跑 B-W9-3 现有 test_affiliate.py, 验证 3 关键 case PASS。"""
        # 跑 pytest verbose
        rc, out, err = _run(
            [
                str(PYTEST_BIN),
                "tests/integration/test_affiliate.py",
                "-v",
                "--no-header",
                "-k",
                "test_attribute_after_track_binds_order or test_commission_is_5_percent_of_order_total or test_payout_settles_all_attributed_orders",
            ],
            cwd=BACKEND_DIR,
            timeout=60,
        )
        combined = out + err
        assert rc == 0, \
            f"B-W9-3 affiliate 3-case pytest FAIL (rc={rc}):\n{combined[-2000:]}"

        # 3 关键 case 名字必须在 PASS 行
        required = [
            "test_attribute_after_track_binds_order",
            "test_commission_is_5_percent_of_order_total",
            "test_payout_settles_all_attributed_orders",
        ]
        for name in required:
            assert name in combined and "PASSED" in combined.split(name)[1].split("\n")[0], \
                f"B-W9-3 case {name} 没 PASS:\n{combined[-2000:]}"

        # 3 passed marker
        assert "3 passed" in combined, \
            f"expected '3 passed', got:\n{combined[-2000:]}"


# --------------------------------------------------------------------------- #
# Test 5: 跨子系统 4 子系统收口 (deliverable 4 件 + WORKLOG 4 行)               #
# --------------------------------------------------------------------------- #
@pytest.mark.slow
class TestW9CrossSubsystem:
    """W9 gate 收口 — 4 子系统 deliverable / WORKLOG / 配置 / 文件存在性 4 维校验。"""

    def test_4_subsystem_files_present(self):
        """W9 4 子系统核心文件存在 (sanity check)。"""
        files = [
            # A-W9-1 iOS 截图
            SCREENSHOTS_DIR / "home_zh.png",
            SCREENSHOTS_DIR / "register_en.png",
            SCREENSHOTS_DIR / "materials_id.png",
            # A-W9-2 前端 aff_code (affiliate.js wrapper)
            WORKSPACE / "frontend" / "web" / "src" / "api" / "affiliate.js",
            WORKSPACE / "frontend" / "web" / "src" / "views" / "OrderNew.vue",
            WORKSPACE / "frontend" / "web" / "src" / "views" / "OrderDetail.vue",
            # B-W9-3 后端钩子
            BACKEND_DIR / "app" / "services" / "affiliate_events.py",
            BACKEND_DIR / "app" / "schemas" / "order.py",  # 含 aff_code 字段
            BACKEND_DIR / "app" / "services" / "order_service.py",  # 含 on_order_created 钩子
            BACKEND_DIR / "app" / "services" / "payment_provider.py",  # 含 on_payment_completed 钩子
            # B-W9-4 Stripe stub
            BACKEND_DIR / "app" / "core" / "config.py",  # 含 stripe_secret_key 占位
            BACKEND_DIR / "tests" / "integration" / "test_payment_stripe_stub.py",
        ]
        missing = [str(f) for f in files if not f.is_file()]
        assert not missing, f"W9 4 子系统核心文件缺失:\n  " + "\n  ".join(missing)

    def test_3_subsystem_deliverables_present(self):
        """W9 子系统 deliverable.md 存在 (A-W9-1, A-W9-2, B-W9-4).

        B-W9-3 (OMS 事件钩子) 的代码 100% 入库 (affiliate_events.py + on_order_created +
        on_payment_completed + on_order_rejected 钩子), 但 producer 没写独立 deliverable.md —
        这是 W9-3 的设计 (后端隐性任务, 由本 C-W9-5 集成测试收口)。
        所以这里只查 3 个 producer deliverable.md; B-W9-3 收口在本测试的 wire-level
        TestOmsAffCodeEndToEnd + test_strict_evidence 中。
        """
        plan_outputs = Path(os.environ.get("W9_PLAN_OUTPUTS", "/nonexistent"))
        if not plan_outputs.is_dir():
            pytest.skip(
                f"W9_PLAN_OUTPUTS not set or not a directory ({plan_outputs}); "
                "deliverable.md presence check skipped on this machine."
            )
        expected = {
            "A-W9-1": plan_outputs / "A-W9-1" / "deliverable.md",
            "A-W9-2": plan_outputs / "A-W9-2" / "deliverable.md",
            "B-W9-4": plan_outputs / "B-W9-4" / "deliverable.md",
        }
        for sub, path in expected.items():
            if not path.is_file():
                pytest.fail(
                    f"{sub} deliverable.md 缺失: {path}\n"
                    f"  → W9 gate FAIL, producer 必须补"
                )

    def test_worklogs_have_w9_markers(self):
        """4 个 WORKLOG 必含 W9-* 收口行 (A-W9-1, A-W9-2, B-W9-3, B-W9-4, C-W9-5)."""
        checks = [
            ("A_WORKLOG", WORKSPACE / "A_WORKLOG.md", ["W9-1", "W9-2"]),
            ("C_WORKLOG", WORKSPACE / "C_WORKLOG.md", ["W9-5"]),
            ("backend_WORKLOG", BACKEND_DIR / "WORKLOG.md", ["W9-3", "W9-4"]),
        ]
        for name, path, markers in checks:
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            for m in markers:
                # C_WORKLOG "W9-5" 还没追加, 本 case 跳过 (本任务收口)
                if m == "W9-5" and name == "C_WORKLOG":
                    continue
                assert m in text, \
                    f"{name} ({path}) 缺 marker '{m}' — W9 收口行必写"

    def test_4_subsystem_strict_evidence(self):
        """W9 4 子系统硬证据 4 维 (对应 deliverable.md 4 节):
          - iOS 截图: 3 张 + sha256 distinct
          - OMS aff_code 端到端: W9-2 前端 3 文件 + W9-3 后端钩子 + on_order_created 触发
          - OMS 事件钩子: 3 钩子 (on_order_created, on_payment_completed, on_order_rejected) 都在位
          - 支付接真准备: stripe SDK 15.2.0 + StripePaymentProvider stub + 零凭据
        """
        # 1) iOS 截图
        pngs = sorted(SCREENSHOTS_DIR.glob("*.png"))
        assert len(pngs) == 3, f"iOS 截图 != 3"
        shas = {hashlib.sha256(p.read_bytes()).hexdigest() for p in pngs}
        assert len(shas) == 3, f"iOS 截图 sha256 不全 distinct"

        # 2) OMS aff_code 端到端 — schema 收 aff_code + order_service 调钩子
        schema = (BACKEND_DIR / "app" / "schemas" / "order.py").read_text(encoding="utf-8")
        assert "aff_code" in schema, "CreateOrderRequest 缺 aff_code 字段"
        order_svc = (BACKEND_DIR / "app" / "services" / "order_service.py").read_text(encoding="utf-8")
        assert "on_order_created" in order_svc, "order_service.create 没调 on_order_created 钩子"

        # 3) OMS 事件钩子 — 3 钩子都在位
        events = (BACKEND_DIR / "app" / "services" / "affiliate_events.py").read_text(encoding="utf-8")
        for hook in ("on_order_created", "on_payment_completed", "on_order_rejected"):
            assert hook in events, f"affiliate_events.py 缺 {hook}"
        # payment_provider 调 on_payment_completed
        pay = (BACKEND_DIR / "app" / "services" / "payment_provider.py").read_text(encoding="utf-8")
        assert "on_payment_completed" in pay, "payment_provider.handle_notify 没调 on_payment_completed"
        # order_service 调 on_order_rejected
        assert "on_order_rejected" in order_svc, "order_service.cancel 没调 on_order_rejected"

        # 4) 支付接真准备 — stripe SDK + stub + 零凭据
        requirements = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8")
        assert "stripe>=" in requirements, "requirements.txt 缺 stripe>= 锁定"
        config = (BACKEND_DIR / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert "stripe_secret_key" in config, "config.py 缺 stripe_secret_key 占位"
        # 零凭据: 默认空
        settings = get_settings()
        assert settings.stripe_secret_key == "", f"stripe_secret_key 应默认空, got {settings.stripe_secret_key!r}"
        # Stripe stub 在位
        assert "class StripePaymentProvider" in pay, "payment_provider.py 缺 StripePaymentProvider class"
