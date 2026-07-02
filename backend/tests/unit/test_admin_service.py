"""Unit tests for app.services.admin_service — W14-3.

Uses an isolated tmpfile SQLite DB (see test_admin_service_conftest.py).
The `tmp_db` fixture provides a per-test AsyncSession on an empty temp DB.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.core.errors import ErrorCode
from app.services.admin_service import AdminService


# --------------------------------------------------------------------------- #
# Login — no DB writes needed for credential check                           #
# --------------------------------------------------------------------------- #

class TestAdminLogin:
    async def test_login_correct_credentials_returns_token(self, tmp_db: Any):
        """Valid admin credentials return a JWT with Bearer token."""
        svc = AdminService(tmp_db)
        result = await svc.login(username="admin", password="visa-admin-2024")
        assert result["token_type"] == "Bearer"
        assert result["access_token"].count(".") == 2
        assert result["expires_in"] > 0

    async def test_login_wrong_password_raises(self, tmp_db: Any):
        """Wrong password raises AUTH_INVALID_CREDENTIALS."""
        svc = AdminService(tmp_db)
        with pytest.raises(Exception) as exc:
            await svc.login(username="admin", password="wrong")
        assert exc.value.code == ErrorCode.AUTH_INVALID_CREDENTIALS

    async def test_login_wrong_username_raises(self, tmp_db: Any):
        """Wrong username raises AUTH_INVALID_CREDENTIALS."""
        svc = AdminService(tmp_db)
        with pytest.raises(Exception) as exc:
            await svc.login(username="not-admin", password="visa-admin-2024")
        assert exc.value.code == ErrorCode.AUTH_INVALID_CREDENTIALS


# --------------------------------------------------------------------------- #
# User management                                                           #
# --------------------------------------------------------------------------- #

class TestAdminUserManagement:
    async def test_list_users_paginated_empty(self, tmp_db: Any):
        """Empty DB returns zero items."""
        svc = AdminService(tmp_db)
        result = await svc.list_users(page=1, page_size=20)
        assert result["items"] == []
        assert result["page"] == 1
        assert result["total"] == 0

    async def test_get_user_not_found_raises(self, tmp_db: Any):
        """Non-existent user raises USER_NOT_FOUND."""
        svc = AdminService(tmp_db)
        with pytest.raises(Exception) as exc:
            await svc.get_user(user_id=99999)
        assert exc.value.code == ErrorCode.USER_NOT_FOUND


# --------------------------------------------------------------------------- #
# Order management                                                           #
# --------------------------------------------------------------------------- #

class TestAdminOrderManagement:
    async def test_list_orders_empty(self, tmp_db: Any):
        """Empty DB returns zero items."""
        svc = AdminService(tmp_db)
        result = await svc.list_orders(page=1, page_size=20)
        assert result["items"] == []
        assert result["total"] == 0

    async def test_get_order_not_found_raises(self, tmp_db: Any):
        """Non-existent order raises ORDER_NOT_FOUND."""
        svc = AdminService(tmp_db)
        with pytest.raises(Exception) as exc:
            await svc.get_order(order_id=99999)
        assert exc.value.code == ErrorCode.ORDER_NOT_FOUND

    async def test_update_order_invalid_status_raises(self, tmp_db: Any):
        """Order not found (before status check) raises ORDER_NOT_FOUND."""
        svc = AdminService(tmp_db)
        with pytest.raises(Exception) as exc:
            await svc.update_order_status(order_id=99999, new_status="invalid_status")
        assert exc.value.code == ErrorCode.ORDER_NOT_FOUND


# --------------------------------------------------------------------------- #
# Country config                                                             #
# --------------------------------------------------------------------------- #

class TestAdminCountryConfig:
    async def test_list_countries_empty(self, tmp_db: Any):
        """Empty visa_countries table returns zero items."""
        svc = AdminService(tmp_db)
        result = await svc.list_countries(page=1, page_size=50)
        assert result["items"] == []
        assert result["total"] == 0

    async def test_update_country_not_found_raises(self, tmp_db: Any):
        """Non-existent country raises NOT_FOUND."""
        svc = AdminService(tmp_db)
        with pytest.raises(Exception) as exc:
            await svc.update_country(country_id=99999, data={})
        assert exc.value.code == ErrorCode.NOT_FOUND

    async def test_delete_country_not_found_raises(self, tmp_db: Any):
        """Delete non-existent country raises NOT_FOUND."""
        svc = AdminService(tmp_db)
        with pytest.raises(Exception) as exc:
            await svc.delete_country(country_id=99999)
        assert exc.value.code == ErrorCode.NOT_FOUND


# --------------------------------------------------------------------------- #
# RPA config — no DB needed                                                  #
# --------------------------------------------------------------------------- #

class TestAdminRpaConfig:
    def test_get_rpa_config_returns_dict(self):
        """RPA config loads from YAML file (no DB needed)."""
        svc = AdminService(db=None)
        result = svc.get_rpa_config()
        assert isinstance(result, dict)

    async def test_update_rpa_config_returns_dict(self, tmp_db):
        """Updating RPA config returns merged config."""
        svc = AdminService(db=tmp_db)
        result = await svc.update_rpa_config({"mock_mode": False})
        assert isinstance(result, dict)
        assert result.get("mock_mode") is False


# --------------------------------------------------------------------------- #
# RPA stats                                                                  #
# --------------------------------------------------------------------------- #

class TestAdminRpaStats:
    async def test_get_rpa_stats_returns_zero_baseline(self, tmp_db: Any):
        """Empty scheduler returns zeroed stats with sane shapes."""
        svc = AdminService(tmp_db)
        stats = svc.get_rpa_stats()
        assert isinstance(stats, dict)
        assert stats["today_visits"] >= 0
        assert stats["queued_tasks"] >= 0
        assert 0.0 <= stats["failure_rate_24h"] <= 1.0
        assert stats["total_count_24h"] >= 0
        assert stats["failed_count_24h"] <= stats["total_count_24h"]
        assert stats["success_count_24h"] >= 0
        assert stats["active_accounts"] >= 0
        assert stats["sample_window_seconds"] == 86400
        assert stats["generated_at"] is not None


# --------------------------------------------------------------------------- #
# Audit logs                                                                 #
# --------------------------------------------------------------------------- #

class TestAdminLogs:
    async def test_list_logs_paginated(self, tmp_db: Any):
        """Empty audit_log table returns zero items."""
        svc = AdminService(tmp_db)
        result = await svc.list_logs(page=1, page_size=50)
        assert result["items"] == []
        assert result["total"] == 0