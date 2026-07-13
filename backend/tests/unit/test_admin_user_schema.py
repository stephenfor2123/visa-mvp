"""Admin user schema — masking + list/detail count fields."""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.admin import UserDetailOut, UserListItem


def test_user_list_item_from_raw_preserves_counts():
    raw = {
        "id": 7,
        "uuid": "u-0007",
        "email": "zhangwei@gmail.com",
        "username": "zhang_wei",
        "nickname": "小张",
        "language_pref": "zh-CN",
        "status": "active",
        "mfa_enabled": False,
        "created_at": datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
        "order_count": 3,
        "material_count": 5,
    }
    item = UserListItem.from_raw(raw)
    assert item.id == 7
    assert item.nickname == "小张"
    assert item.email == "zh***@gmail.com"
    assert item.order_count == 3
    assert item.material_count == 5


def test_user_detail_out_from_raw_preserves_counts():
    raw = {
        "id": 9,
        "uuid": "u-0009",
        "email": "demo@htex.test",
        "username": "demo_user",
        "nickname": "Demo",
        "language_pref": "en",
        "status": "active",
        "mfa_enabled": True,
        "created_at": datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
        "order_count": 2,
        "material_count": 4,
    }
    detail = UserDetailOut.from_raw(raw)
    assert detail.order_count == 2
    assert detail.material_count == 4
