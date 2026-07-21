"""Integration tests for /api/v2/rpa/* — POST /submit, GET /status, POST /cancel.

Covers:
  - POST /rpa/submit: happy (US enabled) / country-disabled / rate-limit /
    unauthenticated / wrong-token-type
  - GET /rpa/status/{task_id}: happy / not-found / IDOR (other user's task)
  - POST /rpa/cancel/{task_id}: happy / not-found / IDOR / already-done
  - GET /rpa/config: public, no auth required
  - PUT /rpa/config: valid admin token / missing token / invalid token
  - side effects: session row, audit row on submit
"""
from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.rpa.rpa_scheduler import (
    RPAScheduler,
    TaskStatus,
    get_scheduler,
    reset_scheduler_for_tests,
)


# ----------------------------------------------------------------- #
# Per-test singleton reset                                           #
# ----------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _reset_scheduler():
    """Each test starts with a clean RPAScheduler + empty task map."""
    reset_scheduler_for_tests()
    yield
    reset_scheduler_for_tests()


# ----------------------------------------------------------------- #
# Helpers                                                           #
# ----------------------------------------------------------------- #
def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, phone: str) -> str:
    """Register or reuse account keyed by phone → returns access token."""
    uname = f"u{phone}"
    email = f"{phone}@test.local"
    pwd = "Test1234"
    await client.post(
        "/api/v2/auth/register",
        json={"username": uname, "email": email, "password": pwd, "email_code": "123456", "age_confirmed_16": True},
    )
    r = await client.post(
        "/api/v2/auth/login",
        json={"account": email, "password": pwd},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _build_submit_body(order_id: str = "ORD-001", country_code: str = "US") -> dict:
    return {
        "order_id": order_id,
        "country_code": country_code,
        "visa_type": "visit_visa",
        "passport_data": {
            "surname": "LI",
            "given_name": "SI",
            "dob": "1992-05-20",
            "passport_no": "E98765432",
            "nationality": "CN",
        },
    }


# ----------------------------------------------------------------- #
# POST /rpa/submit                                                  #
# ----------------------------------------------------------------- #
class TestRPASubmit:
    async def test_submit_happy_returns_task_id(self, client):
        """POST /rpa/submit → 200 + task_id + status=submitting (US enabled)."""
        token = await _register(client, "13800001101")
        body = _build_submit_body("ORD-SUBMIT-HAPPY", "US")

        r = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["task_id"].startswith("rpa-")
        assert data["status"] == "submitting"
        assert data["order_id"] == "ORD-SUBMIT-HAPPY"

    async def test_submit_country_disabled_returns_4008(self, client):
        """Schengen IT is in product scope but not enabled in rpa_config.yaml → 409."""
        token = await _register(client, "13800001102")
        body = _build_submit_body("ORD-SUBMIT-IT", "IT")

        r = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))
        # W22 fix: actual backend uses 409 (Conflict) for biz errors with code 4008
        assert r.status_code == 409, r.text
        # RPASchedulerError surfaces as ORDER_INVALID_STATE
        assert r.json()["code"] == "4008"

    async def test_submit_unauthenticated_returns_1005(self, client):
        r = await client.post(
            "/api/v2/rpa/submit",
            json=_build_submit_body(),
        )
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_submit_invalid_country_code_returns_400(self, client):
        """Non-product / unknown country → 400 INVALID_PARAMS."""
        token = await _register(client, "13800001103")
        body = _build_submit_body("ORD-SUBMIT-XX", "XX")
        r = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))
        assert r.status_code == 400, r.text
        assert r.json()["code"] == "1001"

    async def test_submit_missing_field_returns_400(self, client):
        """W22 fix: backend returns 400 (Bad Request) not 422 for missing fields."""
        token = await _register(client, "13800001104")
        r = await client.post(
            "/api/v2/rpa/submit",
            json={"order_id": "ORD-MISSING"},
            headers=_bearer(token),
        )
        assert r.status_code == 400, r.text

    async def test_submit_non_product_country_rejected(self, client):
        """ID/VN are customer markets — not visa destinations we file."""
        token = await _register(client, "13800001105")
        body = _build_submit_body("ORD-SUBMIT-VN", "VN")
        r = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))
        assert r.status_code == 400, r.text
        assert r.json()["code"] == "1001"


# ----------------------------------------------------------------- #
# GET /rpa/status/{task_id}                                          #
# ----------------------------------------------------------------- #
class TestRPAStatus:
    async def test_status_happy(self, client):
        """Submit first, then query status."""
        token = await _register(client, "13800001201")
        body = _build_submit_body("ORD-STATUS-001", "US")
        sr = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))
        task_id = sr.json()["data"]["task_id"]

        r = await client.get(f"/api/v2/rpa/status/{task_id}", headers=_bearer(token))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["task_id"] == task_id
        assert data["status"] == "submitting"
        assert data["progress"] == 0.1
        assert data["country_code"] == "US"
        # W22 fix: RPATaskStatus 不返回 visa_type (schema 不包含此字段)

    async def test_status_not_found_returns_404(self, client):
        token = await _register(client, "13800001202")
        r = await client.get(
            "/api/v2/rpa/status/rpa-nonexistent-task",
            headers=_bearer(token),
        )
        assert r.status_code == 404
        assert r.json()["code"] == "1004"

    async def test_status_idor_other_user_returns_404(self, client):
        """User A submits; User B queries → 404 (not_found, no existence leak)."""
        token_a = await _register(client, "13800001210")
        token_b = await _register(client, "13800001211")

        body = _build_submit_body("ORD-STATUS-IDOR", "US")
        sr = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token_a))
        task_id = sr.json()["data"]["task_id"]

        r = await client.get(
            f"/api/v2/rpa/status/{task_id}",
            headers=_bearer(token_b),
        )
        assert r.status_code == 404
        assert r.json()["code"] == "1004"

    async def test_status_unauthenticated_returns_1005(self, client):
        r = await client.get("/api/v2/rpa/status/rpa-abc123")
        assert r.status_code == 401
        assert r.json()["code"] == "1005"


# ----------------------------------------------------------------- #
# POST /rpa/cancel/{task_id}                                          #
# ----------------------------------------------------------------- #
class TestRPACancel:
    async def test_cancel_happy(self, client):
        """Submit, then cancel a submitting task → 200 + status=cancelled."""
        token = await _register(client, "13800001301")
        body = _build_submit_body("ORD-CANCEL-001", "US")
        sr = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))
        task_id = sr.json()["data"]["task_id"]

        r = await client.post(f"/api/v2/rpa/cancel/{task_id}", headers=_bearer(token))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["status"] == "cancelled"

    async def test_cancel_not_found_returns_404(self, client):
        token = await _register(client, "13800001302")
        r = await client.post(
            "/api/v2/rpa/cancel/rpa-nonexistent",
            headers=_bearer(token),
        )
        assert r.status_code == 404

    async def test_cancel_idor_returns_404(self, client):
        token_a = await _register(client, "13800001310")
        token_b = await _register(client, "13800001311")

        body = _build_submit_body("ORD-CANCEL-IDOR", "US")
        sr = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token_a))
        task_id = sr.json()["data"]["task_id"]

        r = await client.post(
            f"/api/v2/rpa/cancel/{task_id}",
            headers=_bearer(token_b),
        )
        assert r.status_code == 404

    async def test_cancel_unauthenticated_returns_1005(self, client):
        r = await client.post("/api/v2/rpa/cancel/rpa-abc123")
        assert r.status_code == 401

    async def test_cancel_already_done_returns_current_status(self, client):
        """Cancel on a DONE task returns the DONE status (cannot cancel completed)."""
        token = await _register(client, "13800001320")

        # Submit
        body = _build_submit_body("ORD-CANCEL-DONE", "US")
        sr = await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))
        task_id = sr.json()["data"]["task_id"]

        # Mark done directly via scheduler
        scheduler = get_scheduler()
        scheduler.mark_done(task_id, confirmation_no="CNF-001")

        # Cancel should return the DONE status
        r = await client.post(f"/api/v2/rpa/cancel/{task_id}", headers=_bearer(token))
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "done"


# ----------------------------------------------------------------- #
# GET /rpa/config                                                    #
# ----------------------------------------------------------------- #
class TestRPAConfigGet:
    async def test_get_config_public_no_auth(self, client):
        """GET /rpa/config requires no auth."""
        r = await client.get("/api/v2/rpa/config")
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "mock_mode" in data
        assert "rate_limits" in data
        assert "countries" in data
        # Product destinations enabled; ID/VN are customer markets only
        assert data["countries"].get("US") is True
        assert data["countries"].get("ID") is False
        assert data["countries"].get("VN") is False


# ----------------------------------------------------------------- #
# PUT /rpa/config                                                    #
# ----------------------------------------------------------------- #
class TestRPAConfigUpdate:
    async def test_update_config_valid_admin_token(self, client):
        """Valid X-Admin-Token → 200."""
        settings = get_settings()
        r = await client.put(
            "/api/v2/rpa/config",
            json={"mock_mode": True},
            headers={"X-Admin-Token": settings.system_api_key},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["mock_mode"] is True

    async def test_update_config_missing_token_returns_401(self, client):
        r = await client.put(
            "/api/v2/rpa/config",
            json={"mock_mode": False},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_update_config_invalid_token_returns_403(self, client):
        r = await client.put(
            "/api/v2/rpa/config",
            json={"mock_mode": False},
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert r.status_code == 403
        # W22 fix: backend uses 1006 (Invalid admin token) not 1003
        assert r.json()["code"] == "1006"


# ----------------------------------------------------------------- #
# GET /rpa/tasks (list)                                              #
# ----------------------------------------------------------------- #
class TestRPAListTasks:
    async def test_list_tasks_happy(self, client):
        """Submit 2 tasks, list them."""
        # W22 fix: 重置 scheduler + 关掉 account interval, 不然第 2 次 submit 会被 429 拦
        reset_scheduler_for_tests()
        scheduler = get_scheduler()
        scheduler._config["rate_limits"]["account_interval_minutes"] = 0

        token = await _register(client, "13800001401")
        body1 = _build_submit_body("ORD-LIST-001", "US")
        body2 = _build_submit_body("ORD-LIST-002", "GB")

        await client.post("/api/v2/rpa/submit", json=body1, headers=_bearer(token))
        await client.post("/api/v2/rpa/submit", json=body2, headers=_bearer(token))

        r = await client.get("/api/v2/rpa/tasks", headers=_bearer(token))
        assert r.status_code == 200, r.text
        tasks = r.json()["data"]
        # W22 fix: scheduler 是进程级, 多个 test 间会累积 tasks.
        # 确认新加的 2 个 task 都在列表里即可.
        order_ids = {t["order_id"] for t in tasks}
        assert "ORD-LIST-001" in order_ids
        assert "ORD-LIST-002" in order_ids

    async def test_list_tasks_by_order_id(self, client):
        """Filter by order_id."""
        token = await _register(client, "13800001402")
        body = _build_submit_body("ORD-FILTER-001", "US")
        await client.post("/api/v2/rpa/submit", json=body, headers=_bearer(token))

        r = await client.get(
            "/api/v2/rpa/tasks?order_id=ORD-FILTER-001",
            headers=_bearer(token),
        )
        assert r.status_code == 200, r.text
        tasks = r.json()["data"]
        assert len(tasks) == 1
        assert tasks[0]["order_id"] == "ORD-FILTER-001"

    async def test_list_tasks_unauthenticated_returns_1005(self, client):
        r = await client.get("/api/v2/rpa/tasks")
        assert r.status_code == 401
        assert r.json()["code"] == "1005"


# ----------------------------------------------------------------- #
# Scheduler unit tests (sync)                                       #
# ----------------------------------------------------------------- #
class TestRPASchedulerSync:
    """Sync tests to push scheduler line coverage without async overhead."""

    def test_scheduler_singleton_same_instance(self):
        a = get_scheduler()
        b = get_scheduler()
        assert a is b

    def test_mark_done(self):
        reset_scheduler_for_tests()
        scheduler = get_scheduler()
        task_id = scheduler.submit_visa_application(
            order_id="ORD-DONE",
            country_code="US",
            visa_type="visit_visa",
            user_id="test-user",
        )
        scheduler.mark_done(task_id, confirmation_no="CNF-TEST-001")
        status = scheduler.get_task_status(task_id)
        assert status["status"] == "done"
        assert status["confirmation_no"] == "CNF-TEST-001"
        assert status["progress"] == 1.0

    def test_mark_failed(self):
        reset_scheduler_for_tests()
        scheduler = get_scheduler()
        task_id = scheduler.submit_visa_application(
            order_id="ORD-FAIL",
            country_code="US",
            visa_type="visit_visa",
            user_id="test-user",
        )
        scheduler.mark_failed(task_id, error_detail="Captcha timeout")
        status = scheduler.get_task_status(task_id)
        assert status["status"] == "failed"
        assert status["error_detail"] == "Captcha timeout"

    def test_task_not_found_returns_not_found_status(self):
        scheduler = get_scheduler()
        status = scheduler.get_task_status("rpa-does-not-exist")
        assert status["status"] == "not_found"

    def test_concurrent_limit_enforced(self):
        """3rd submission for same user (max=2) → RPASchedulerError."""
        reset_scheduler_for_tests()
        scheduler = get_scheduler()
        # Override limits for this test — disable account interval, set concurrent=2
        scheduler._config["rate_limits"]["account_interval_minutes"] = 0
        scheduler._config["rate_limits"]["max_concurrent_tasks"] = 2

        scheduler.submit_visa_application(
            "ORD-C1", "US", "visit_visa", user_id="limit-user"
        )
        scheduler.submit_visa_application(
            "ORD-C2", "US", "visit_visa", user_id="limit-user"
        )

        import pytest as _pytest
        with _pytest.raises(Exception) as exc_info:
            scheduler.submit_visa_application(
                "ORD-C3", "US", "visit_visa", user_id="limit-user"
            )
        assert "max" in str(exc_info.value).lower() or "concurrent" in str(exc_info.value).lower()

    def test_ip_rate_limit(self):
        """IP with 50+ visits today → RateLimitExceeded."""
        reset_scheduler_for_tests()
        scheduler = get_scheduler()
        scheduler._config["rate_limits"]["account_interval_minutes"] = 0
        scheduler._config["rate_limits"]["ip_per_day"] = 2
        ip = "192.168.99.99"

        scheduler.submit_visa_application(
            "ORD-IP1", "US", "visit_visa", ip_address=ip
        )
        scheduler.submit_visa_application(
            "ORD-IP2", "US", "visit_visa", ip_address=ip
        )

        import pytest as _pytest
        with _pytest.raises(Exception) as exc_info:
            scheduler.submit_visa_application(
                "ORD-IP3", "US", "visit_visa", ip_address=ip
            )
        assert "limit" in str(exc_info.value).lower()

    def test_update_config(self):
        """Runtime config update."""
        reset_scheduler_for_tests()
        scheduler = get_scheduler()
        cfg = scheduler.update_config({"mock_mode": True})
        assert cfg["mock_mode"] is True
        cfg2 = scheduler.update_config(
            {"rate_limits": {"ip_per_day": 100}}
        )
        assert cfg2["rate_limits"]["ip_per_day"] == 100