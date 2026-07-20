"""
Unit tests for RPA scheduler.

Coverage:
  - submit_visa_application creates task
  - Task state transitions
  - IP rate limit enforcement
  - Account interval enforcement
  - Concurrent task limit
  - get_task_status
  - cancel_task
  - mark_done / mark_failed
  - Config loading and update
  - list_tasks
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


class TestRPASchedulerInit:
    """Test RPAScheduler initialization."""

    def test_init_default(self, tmp_path):
        """Scheduler initializes with default config."""
        from app.services.rpa.rpa_scheduler import RPAScheduler

        scheduler = RPAScheduler(config_path=str(tmp_path / "nonexistent.yaml"))
        assert scheduler.mock_mode is True
        config = scheduler.get_config()
        assert "rate_limits" in config
        assert config["rate_limits"]["ip_per_day"] == 50

    def test_init_with_custom_config(self, tmp_path):
        """Custom config is loaded correctly."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        config_data = {
            "mock_mode": False,
            "rate_limits": {"ip_per_day": 10, "account_interval_minutes": 60},
            "timeouts": {"http_timeout": 45},
            "countries": {
                "ID": {"enabled": True, "base_url": "https://example.com"},
                "VN": {"enabled": True},
            },
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        config = scheduler.get_config()
        assert config["rate_limits"]["ip_per_day"] == 10
        assert config["mock_mode"] is False


class TestSubmitVisaApplication:
    """Test RPA task submission."""

    def test_submit_creates_task(self, tmp_path):
        """submit_visa_application creates a new task and returns task_id."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "countries": {"US": {"enabled": True}}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        task_id = scheduler.submit_visa_application(
            order_id="V2-20260614-000001",
            country_code="US",
            visa_type="visit_visa",
            user_id="user_123",
            ip_address="192.168.1.1",
        )

        assert task_id.startswith("rpa-")
        assert len(task_id) == 15  # "rpa-" (4) + 11 hex chars

        status = scheduler.get_task_status(task_id)
        assert status["status"] == "submitting"
        assert status["order_id"] == "V2-20260614-000001"
        assert status["country_code"] == "US"
        assert status["progress"] > 0

    def test_submit_disabled_country_raises(self, tmp_path):
        """Submitting to a disabled country raises RPASchedulerError."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler, RPASchedulerError

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "countries": {"US": {"enabled": False}}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))

        with pytest.raises(RPASchedulerError) as exc_info:
            scheduler.submit_visa_application("order_1", "US", "visit_visa")
        assert "not enabled" in str(exc_info.value)


class TestRateLimiting:
    """Test rate limit enforcement."""

    def test_ip_rate_limit_exceeded(self, tmp_path):
        """IP daily limit is enforced."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler, RateLimitExceeded

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({
                "mock_mode": True,
                "rate_limits": {"ip_per_day": 2, "account_interval_minutes": 0},
                "countries": {"ID": {"enabled": True}},
            }, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        ip = "10.0.0.1"

        # First two should succeed
        t1 = scheduler.submit_visa_application("order_1", "ID", "visit_visa", ip_address=ip)
        t2 = scheduler.submit_visa_application("order_2", "ID", "visit_visa", ip_address=ip)

        # Third should fail with RateLimitExceeded
        with pytest.raises(RateLimitExceeded) as exc_info:
            scheduler.submit_visa_application("order_3", "ID", "visit_visa", ip_address=ip)
        assert "daily limit" in str(exc_info.value)

    def test_account_interval_enforced(self, tmp_path):
        """Account submission interval is enforced."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler, RateLimitExceeded

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({
                "mock_mode": True,
                "rate_limits": {"ip_per_day": 100, "account_interval_minutes": 30},
                "countries": {"ID": {"enabled": True}},
            }, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        user = "user_interval_test"

        # First submit
        scheduler.submit_visa_application("order_1", "ID", "visit_visa", user_id=user)

        # Immediate second submit should fail
        with pytest.raises(RateLimitExceeded) as exc_info:
            scheduler.submit_visa_application("order_2", "ID", "visit_visa", user_id=user)
        assert "wait" in str(exc_info.value).lower()

    def test_concurrent_task_limit(self, tmp_path):
        """Max concurrent tasks per account is enforced."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler, RPASchedulerError

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({
                "mock_mode": True,
                "rate_limits": {"max_concurrent_tasks": 2, "account_interval_minutes": 0},
                "countries": {"ID": {"enabled": True}},
            }, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        user = "user_concurrent_test"

        # Two concurrent tasks should succeed
        scheduler.submit_visa_application("order_1", "ID", "visit_visa", user_id=user)
        scheduler.submit_visa_application("order_2", "ID", "visit_visa", user_id=user)

        # Third concurrent task should fail
        with pytest.raises(RPASchedulerError) as exc_info:
            scheduler.submit_visa_application("order_3", "ID", "visit_visa", user_id=user)
        assert "active tasks" in str(exc_info.value)


class TestTaskStatus:
    """Test task status retrieval."""

    def test_get_task_status_not_found(self):
        """get_task_status returns not_found for unknown task_id."""
        from app.services.rpa.rpa_scheduler import RPAScheduler

        scheduler = RPAScheduler()
        status = scheduler.get_task_status("nonexistent-task-id")
        assert status["status"] == "not_found"

    def test_get_task_status_fields(self, tmp_path):
        """get_task_status returns all expected fields."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "countries": {"ID": {"enabled": True}}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        task_id = scheduler.submit_visa_application(
            "order_1", "ID", "visit_visa", user_id="user_1"
        )
        status = scheduler.get_task_status(task_id)

        expected_keys = [
            "task_id", "order_id", "country_code", "visa_type",
            "status", "progress", "message", "confirmation_no",
            "error_detail", "created_at", "updated_at",
        ]
        for key in expected_keys:
            assert key in status, f"Missing key: {key}"


class TestCancelTask:
    """Test task cancellation."""

    def test_cancel_pending_task(self, tmp_path):
        """cancel_task transitions submitting task to cancelled."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler, TaskStatus

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "countries": {"ID": {"enabled": True}}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        task_id = scheduler.submit_visa_application(
            "order_1", "ID", "visit_visa"
        )
        result = scheduler.cancel_task(task_id)
        assert result["status"] == "cancelled"

    def test_cancel_not_found(self):
        """cancel_task returns not_found for unknown task."""
        from app.services.rpa.rpa_scheduler import RPAScheduler

        scheduler = RPAScheduler()
        result = scheduler.cancel_task("fake-task-id")
        assert result["status"] == "not_found"


class TestMarkDoneFailed:
    """Test task completion markers."""

    def test_mark_done(self, tmp_path):
        """mark_done transitions task to DONE with confirmation_no."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "countries": {"ID": {"enabled": True}}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        task_id = scheduler.submit_visa_application(
            "order_1", "ID", "visit_visa"
        )
        scheduler.mark_done(task_id, confirmation_no="CONF-ABC12345")

        status = scheduler.get_task_status(task_id)
        assert status["status"] == "done"
        assert status["confirmation_no"] == "CONF-ABC12345"
        assert status["progress"] == 1.0
        assert status["completed_at"] is not None

    def test_mark_failed(self, tmp_path):
        """mark_failed transitions task to FAILED with error_detail."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "countries": {"ID": {"enabled": True}}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        task_id = scheduler.submit_visa_application(
            "order_1", "ID", "visit_visa"
        )
        scheduler.mark_failed(task_id, error_detail="Captcha solve timeout", message="Submission failed")

        status = scheduler.get_task_status(task_id)
        assert status["status"] == "failed"
        assert status["error_detail"] == "Captcha solve timeout"


class TestListTasks:
    """Test task listing."""

    def test_list_tasks_filter_by_order(self, tmp_path):
        """list_tasks filters by order_id."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "countries": {"ID": {"enabled": True}}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        # Use distinct user_ids so concurrent-task limit (default 2/user) doesn't block.
        scheduler.submit_visa_application("order_X", "ID", "visit_visa", user_id="user_a")
        scheduler.submit_visa_application("order_X", "ID", "visit_visa", user_id="user_b")
        scheduler.submit_visa_application("order_Y", "ID", "visit_visa", user_id="user_c")

        tasks = scheduler.list_tasks(order_id="order_X")
        assert len(tasks) == 2
        for task in tasks:
            assert task["order_id"] == "order_X"


class TestConfigUpdate:
    """Test runtime config updates."""

    def test_update_config_mock_mode(self, tmp_path):
        """update_config can toggle mock_mode."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        assert scheduler.mock_mode is True

        config = scheduler.update_config({"mock_mode": False})
        assert config["mock_mode"] is False

    def test_update_config_rate_limits(self, tmp_path):
        """update_config can update rate limits."""
        import yaml

        from app.services.rpa.rpa_scheduler import RPAScheduler

        config_path = tmp_path / "rpa_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"mock_mode": True, "rate_limits": {"ip_per_day": 50}}, f)

        scheduler = RPAScheduler(config_path=str(config_path))
        config = scheduler.update_config({
            "rate_limits": {"ip_per_day": 100}
        })

        assert config["rate_limits"]["ip_per_day"] == 100