"""Integration tests for /api/v2/admin/* — W14-3 admin panel."""
from __future__ import annotations

import pytest


class TestAdminLogin:
    async def test_login_correct_credentials(self, client):
        r = await client.post(
            "/api/v2/admin/login",
            json={"username": "admin", "password": "visa-admin-2024"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        assert body["data"]["token_type"] == "Bearer"
        assert body["data"]["access_token"].count(".") == 2

    async def test_login_wrong_password(self, client):
        r = await client.post(
            "/api/v2/admin/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"

    async def test_login_wrong_username(self, client):
        r = await client.post(
            "/api/v2/admin/login",
            json={"username": "not-admin", "password": "visa-admin-2024"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "2001"


class TestAdminUsersUnauthenticated:
    async def test_list_users_no_token(self, client):
        r = await client.get("/api/v2/admin/users")
        assert r.status_code == 401
        assert r.json()["code"] == "1005"

    async def test_get_user_no_token(self, client):
        r = await client.get("/api/v2/admin/users/1")
        assert r.status_code == 401

    async def test_delete_user_no_token(self, client):
        r = await client.delete("/api/v2/admin/users/1")
        assert r.status_code == 401


class TestAdminOrdersUnauthenticated:
    async def test_list_orders_no_token(self, client):
        r = await client.get("/api/v2/admin/orders")
        assert r.status_code == 401

    async def test_get_order_no_token(self, client):
        r = await client.get("/api/v2/admin/orders/1")
        assert r.status_code == 401

    async def test_update_order_status_no_token(self, client):
        r = await client.put(
            "/api/v2/admin/orders/1/status",
            json={"status": "reviewing"},
        )
        assert r.status_code == 401


class TestAdminConfigUnauthenticated:
    async def test_list_countries_no_token(self, client):
        r = await client.get("/api/v2/admin/config/countries")
        assert r.status_code == 401

    async def test_get_validation_rules_no_token(self, client):
        r = await client.get("/api/v2/admin/config/validation-rules")
        assert r.status_code == 401

    async def test_get_rpa_config_no_token(self, client):
        r = await client.get("/api/v2/admin/config/rpa")
        assert r.status_code == 401

    async def test_logs_no_token(self, client):
        r = await client.get("/api/v2/admin/logs")
        assert r.status_code == 401


class TestAdminAuthenticated:
    async def _admin_token(self, client):
        r = await client.post(
            "/api/v2/admin/login",
            json={"username": "admin", "password": "visa-admin-2024"},
        )
        return r.json()["data"]["access_token"]

    async def test_list_users_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"
        assert "items" in r.json()["data"]

    async def test_list_orders_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"

    async def test_list_countries_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/config/countries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"

    async def test_list_logs_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"

    async def test_get_rpa_config_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/config/rpa",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"
        assert "mock_mode" in r.json()["data"]

    async def test_create_country_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.post(
            "/api/v2/admin/config/countries",
            json={
                "country_code": "XX",
                "country_name_zh": "测试国",
                "country_name_en": "Test Country",
                "enabled": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        assert r.json()["code"] == "1000"
        assert r.json()["data"]["country_code"] == "XX"

    async def test_create_country_duplicate_conflict(self, client):
        token = await self._admin_token(client)
        # Create first
        await client.post(
            "/api/v2/admin/config/countries",
            json={
                "country_code": "YY",
                "country_name_zh": "重复国",
                "country_name_en": "Duplicate Country",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        # Duplicate
        r2 = await client.post(
            "/api/v2/admin/config/countries",
            json={
                "country_code": "YY",
                "country_name_zh": "重复国2",
                "country_name_en": "Dup 2",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 409
        assert r2.json()["code"] == "1007"

    async def test_update_country_not_found(self, client):
        token = await self._admin_token(client)
        r = await client.put(
            "/api/v2/admin/config/countries/99999",
            json={"enabled": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == "1004"

    async def test_delete_country_not_found(self, client):
        token = await self._admin_token(client)
        r = await client.delete(
            "/api/v2/admin/config/countries/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

    async def test_get_user_not_found(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/users/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == "3001"

    async def test_get_order_not_found(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/orders/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4001"

    async def test_update_order_status_invalid_status(self, client):
        token = await self._admin_token(client)
        r = await client.put(
            "/api/v2/admin/orders/1/status",
            json={"status": "invalid_status"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 409
        assert r.json()["code"] == "4008"

    async def test_update_order_status_not_found(self, client):
        token = await self._admin_token(client)
        r = await client.put(
            "/api/v2/admin/orders/99999/status",
            json={"status": "reviewing"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == "4001"

    async def test_get_validation_rules_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.get(
            "/api/v2/admin/config/validation-rules",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"
        assert isinstance(r.json()["data"], list)

    async def test_update_validation_rules_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.put(
            "/api/v2/admin/config/validation-rules",
            json={
                "rules": [
                    {
                        "code": "NEW_RULE",
                        "rule_type": "regex",
                        "severity": "error",
                        "message_key": "new_rule",
                        "params": {"field": "x", "pattern": "^\\S+$"},
                        "enabled": True,
                    }
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"

    async def test_update_rpa_config_authenticated(self, client):
        token = await self._admin_token(client)
        r = await client.put(
            "/api/v2/admin/config/rpa",
            json={"mock_mode": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["code"] == "1000"

    async def test_delete_user_not_found(self, client):
        token = await self._admin_token(client)
        r = await client.delete(
            "/api/v2/admin/users/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
        assert r.json()["code"] == "3001"

    async def test_soft_delete_user_happy(self, client):
        """Register a user, then soft-delete via admin."""
        # Register user via C-user flow
        await client.post(
            "/api/v2/auth/sms-login",
            json={"phone": "13999990001", "phone_country": "+86", "sms_code": "123456"},
        )
        # Login as admin
        token = await self._admin_token(client)
        # List users to get user_id
        r_list = await client.get(
            "/api/v2/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_list.status_code == 200
        items = r_list.json()["data"]["items"]
        assert len(items) >= 1
        user_id = items[0]["id"]
        # Delete user
        r_del = await client.delete(
            f"/api/v2/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_del.status_code == 200
        assert r_del.json()["code"] == "1000"
