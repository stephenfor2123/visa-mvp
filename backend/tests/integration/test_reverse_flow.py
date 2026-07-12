"""逆向流程回归测试 — 拒绝、异常、资金流水、audit 日志链

覆盖内容:
  1. 订单状态机——管理端驱动的完整拒绝路径 (reviewed→rejected→closed)
  2. 订单状态机——审批通过路径 (reviewing→approved→closed)
  3. 非法状态跳跃被拦截 (不允许 closed→created 等回退)
  4. 用户取消 + 状态历史记录
  5. 资金流水 (admin /payments): 支付创建 → 支付成功 → 记录进列表
  6. 资金流水过滤: status=paid 只返回已付单
  7. Audit 日志链: 每次状态变更都写 audit_log + status_history
  8. 管理端订单详情: 包含完整 status_history + audit_logs + payment 信息
  9. RPA 失败路径: submitted→failed 状态 + audit 日志
 10. 用户被封禁后无法操作 (disabled → 403)
"""
from __future__ import annotations

import io

import pytest

from app.core.db import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.order import Order, OrderStatusHistory
from sqlalchemy import select, desc


# ----------------------------------------------------------------- #
# Helpers                                                            #
# ----------------------------------------------------------------- #
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"FAKE-JPEG-PAYLOAD" * 32


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _admin_bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _sms_login(client, phone: str) -> str:
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


async def _admin_login(client) -> str:
    r = await client.post(
        "/api/v2/admin/login",
        json={"username": "admin", "password": "visa-admin-2024"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _upload(client, token: str) -> int:
    r = await client.post(
        "/api/v2/materials/upload",
        files={"file": ("p.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        data={"material_type": "passport"},
        headers=_bearer(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["material"]["id"]


_DEST_COUNTER = {"n": 0}

async def _ensure_dest(code: str = "ID") -> int:
    """Insert VisaDestination row directly into test DB; return its id."""
    import json as _json
    from app.models.destination import VisaDestination

    async with AsyncSessionLocal() as s:
        existing = await s.scalar(
            select(VisaDestination).where(VisaDestination.country_code == code)
        )
        if existing is not None:
            return existing.id
        _DEST_COUNTER["n"] += 1
        row = VisaDestination(
            country_code=code,
            country_name_i18n=_json.dumps({"zh-CN": code, "en": code}),
            visa_types=_json.dumps(["tourism"]),
            enabled=True,
            display_order=_DEST_COUNTER["n"],
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row.id


async def _create_order(client, user_token: str, dest_id: int, mat_id: int) -> str:
    r = await client.post(
        "/api/v2/orders",
        json={"destination_id": dest_id, "visa_type": "tourism", "material_ids": [mat_id]},
        headers=_bearer(user_token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["order_no"]


async def _submit_order(client, user_token: str, order_no: str) -> None:
    """Submit checklist to move order to submitted."""
    r = await client.get(f"/api/v2/orders/{order_no}/checklist", headers=_bearer(user_token))
    assert r.status_code == 200, r.text
    sig = r.json()["data"]["signature"]
    r2 = await client.post(
        f"/api/v2/orders/{order_no}/submit",
        json={"signature": sig},
        headers=_bearer(user_token),
    )
    assert r2.status_code == 200, r2.text


async def _admin_set_status(client, admin_token: str, order_no: str, status: str, note: str = "") -> dict:
    # Get order id from admin list
    r = await client.get(
        f"/api/v2/admin/orders?order_no={order_no}",
        headers=_admin_bearer(admin_token),
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) >= 1, f"order {order_no} not found in admin list"
    order_id = items[0]["id"]

    r2 = await client.put(
        f"/api/v2/admin/orders/{order_id}/status",
        json={"status": status, "note": note},
        headers=_admin_bearer(admin_token),
    )
    return r2


async def _get_admin_order(client, admin_token: str, order_no: str) -> dict:
    r = await client.get(
        f"/api/v2/admin/orders?order_no={order_no}",
        headers=_admin_bearer(admin_token),
    )
    items = r.json()["data"]["items"]
    order_id = items[0]["id"]
    r2 = await client.get(
        f"/api/v2/admin/orders/{order_id}",
        headers=_admin_bearer(admin_token),
    )
    assert r2.status_code == 200, r2.text
    return r2.json()["data"]


# ----------------------------------------------------------------- #
# 1. 拒绝路径: created → submitted → reviewing → rejected → closed  #
# ----------------------------------------------------------------- #
class TestOrderRejectionPath:
    async def test_full_rejection_path(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13701010001")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        # 1) created → submitted (用户提交)
        await _submit_order(client, user_token, order_no)

        # 2) submitted → reviewing (管理员)
        r = await _admin_set_status(client, admin_token, order_no, "reviewing", "开始审核")
        assert r.status_code == 200, r.text

        # 3) reviewing → rejected (管理员拒绝)
        r = await _admin_set_status(client, admin_token, order_no, "rejected", "材料不全，请补充")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "rejected"

        # 4) rejected → closed (归档)
        r = await _admin_set_status(client, admin_token, order_no, "closed", "拒绝后关闭")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "closed"

        # 5) closed 是终态 — 不可继续流转
        r = await _admin_set_status(client, admin_token, order_no, "created")
        assert r.status_code in (409, 422), f"closed→created 应被拦截，实际 {r.status_code}"

    async def test_status_history_written_at_each_step(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13701010002")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")
        await _admin_set_status(client, admin_token, order_no, "rejected", "信息有误")

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            assert order is not None
            rows = (
                await s.execute(
                    select(OrderStatusHistory)
                    .where(OrderStatusHistory.order_id == order.id)
                    .order_by(OrderStatusHistory.id)
                )
            ).scalars().all()

        # created→submitted, submitted→reviewing, reviewing→rejected の 3 行
        transitions = [(r.from_status, r.to_status) for r in rows]
        assert ("created", "submitted") in transitions
        assert ("submitted", "reviewing") in transitions
        assert ("reviewing", "rejected") in transitions

    async def test_rejected_note_persisted(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13701010003")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")
        rejection_note = "护照照片模糊，请重新上传"
        await _admin_set_status(client, admin_token, order_no, "rejected", rejection_note)

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            row = await s.scalar(
                select(OrderStatusHistory)
                .where(
                    OrderStatusHistory.order_id == order.id,
                    OrderStatusHistory.to_status == "rejected",
                )
        assert row is not None
        assert rejection_note in (row.note or "")


# ----------------------------------------------------------------- #
# 2. 审批通过路径: reviewing → approved → closed                     #
# ----------------------------------------------------------------- #
class TestOrderApprovalPath:
    async def test_full_approval_then_archive(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13702020001")
        dest_id = await _ensure_dest("VN")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")

        r = await _admin_set_status(client, admin_token, order_no, "approved", "审核通过")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "approved"

        # approved → closed (签证出签后归档)
        r = await _admin_set_status(client, admin_token, order_no, "closed", "已出签归档")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "closed"

    async def test_reviewed_at_stamped_on_approval(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13702020002")
        dest_id = await _ensure_dest("VN")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")
        await _admin_set_status(client, admin_token, order_no, "approved")

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
        assert order.reviewed_at is not None, "reviewed_at 应在 approved 时被打上时间戳"


# ----------------------------------------------------------------- #
# 3. 非法状态跳跃被拦截                                             #
# ----------------------------------------------------------------- #
class TestIllegalTransitions:
    async def test_cannot_skip_reviewing(self, client):
        """submitted 不能直接跳 approved，必须经过 reviewing"""
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13703030001")
        dest_id = await _ensure_dest("PH")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        r = await _admin_set_status(client, admin_token, order_no, "approved")
        assert r.status_code in (409, 422), f"submitted→approved 应被拦截: {r.text}"

    async def test_cannot_go_backward(self, client):
        """reviewing 不能退回 submitted"""
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13703030002")
        dest_id = await _ensure_dest("PH")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")
        r = await _admin_set_status(client, admin_token, order_no, "submitted")
        assert r.status_code in (409, 422), f"reviewing→submitted 应被拦截: {r.text}"

    async def test_terminal_state_is_immutable(self, client):
        """closed/abnormal/failed 为终态，不可继续流转"""
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13703030003")
        dest_id = await _ensure_dest("PH")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        # cancel → closed (terminal)
        r = await client.post(
            f"/api/v2/orders/{order_no}/cancel",
            headers=_bearer(user_token),
        )
        assert r.status_code == 200, r.text

        # Try any transition from closed
        r = await _admin_set_status(client, admin_token, order_no, "reviewing")
        assert r.status_code in (409, 422), f"closed→reviewing 应被拦截: {r.text}"


# ----------------------------------------------------------------- #
# 4. 资金流水 (admin /payments)                                      #
# ----------------------------------------------------------------- #
class TestFundFlow:
    async def test_payment_appears_in_fund_flow_after_paid(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13704040001")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        # 发起支付
        r = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 19900, "currency": "USD"},
            headers=_bearer(user_token),
        )
        assert r.status_code in (200, 201), r.text
        trade_no = r.json()["data"]["trade_no"]

        # 模拟支付回调（支付成功）
        await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no, "status": "paid"},
        )

        # 管理端资金流水应包含该订单
        r = await client.get("/api/v2/admin/payments", headers=_admin_bearer(admin_token))
        assert r.status_code == 200, r.text
        items = r.json()["data"]["items"]
        matched = [i for i in items if i["order_no"] == order_no]
        assert len(matched) == 1, f"支付流水中未找到订单 {order_no}"
        record = matched[0]
        assert record["trade_no"] == trade_no
        assert record["amount_cents"] == 19900
        assert record["status"] == "paid"
        assert record["paid_at"] is not None

    async def test_fund_flow_filter_by_status_paid(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13704040002")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        # 仅发起支付，不回调（pending 状态）
        r = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 9900, "currency": "USD"},
            headers=_bearer(user_token),
        )
        assert r.status_code in (200, 201), r.text

        # 用 status=paid 过滤，pending 的订单不应出现
        r = await client.get(
            "/api/v2/admin/payments?status=paid",
            headers=_admin_bearer(admin_token),
        )
        assert r.status_code == 200, r.text
        items = r.json()["data"]["items"]
        nos = [i["order_no"] for i in items]
        assert order_no not in nos, "pending 订单不应出现在 status=paid 过滤结果中"

    async def test_closed_payment_still_visible(self, client):
        """关闭支付后，资金流水仍可查询（状态变 closed）"""
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13704040003")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        r = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 5000, "currency": "USD"},
            headers=_bearer(user_token),
        )
        assert r.status_code in (200, 201), r.text

        # 关闭支付
        r_close = await client.post(
            f"/api/v2/payment/{order_no}/close",
            headers=_bearer(user_token),
        )
        assert r_close.status_code == 200, r_close.text

        r = await client.get(
            "/api/v2/admin/payments?status=closed",
            headers=_admin_bearer(admin_token),
        )
        assert r.status_code == 200, r.text
        items = r.json()["data"]["items"]
        matched = [i for i in items if i["order_no"] == order_no]
        assert len(matched) == 1
        assert matched[0]["status"] == "closed"


# ----------------------------------------------------------------- #
# 5. Audit 日志链                                                    #
# ----------------------------------------------------------------- #
class TestAuditLogChain:
    async def test_audit_log_written_for_every_status_change(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13705050001")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")
        await _admin_set_status(client, admin_token, order_no, "rejected", "材料不合格")

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            logs = (
                await s.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.target_type == "order",
                        AuditLog.target_id == order.id,
                    )
                    .order_by(AuditLog.id)
                )
            ).scalars().all()

        actions = [l.action for l in logs]
        assert "order.create" in actions
        assert "order.submit" in actions
        # admin 状态变更也应写 audit
        admin_actions = [a for a in actions if "order.status" in a or "admin" in a.lower()]
        assert len(admin_actions) >= 2, f"管理端应有 ≥2 条 audit: {actions}"

    async def test_admin_order_detail_includes_audit_and_history(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13705050002")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")

        detail = await _get_admin_order(client, admin_token, order_no)

        # 状态历史
        assert "status_history" in detail, "详情应包含 status_history"
        assert len(detail["status_history"]) >= 2

        # audit 日志
        assert "audit_logs" in detail, "详情应包含 audit_logs"
        assert len(detail["audit_logs"]) >= 1

    async def test_payment_audit_logged(self, client):
        admin_token = await _admin_login(client)
        user_token = await _sms_login(client, "13705050003")
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        r = await client.post(
            "/api/v2/payment/create",
            json={"order_no": order_no, "amount_cents": 19900, "currency": "USD"},
            headers=_bearer(user_token),
        )
        trade_no = r.json()["data"]["trade_no"]
        await client.post(
            "/api/v2/payment/notify",
            json={"order_no": order_no, "trade_no": trade_no, "status": "paid"},
        )

        async with AsyncSessionLocal() as s:
            order = await s.scalar(select(Order).where(Order.order_no == order_no))
            logs = (
                await s.execute(
                    select(AuditLog)
                    .where(AuditLog.target_id == order.id)
                    .order_by(AuditLog.id)
                )
            ).scalars().all()

        actions = [l.action for l in logs]
        pay_actions = [a for a in actions if "pay" in a.lower()]
        assert len(pay_actions) >= 1, f"应有支付相关 audit 日志: {actions}"


# ----------------------------------------------------------------- #
# 6. RPA 失败路径                                                    #
# ----------------------------------------------------------------- #
class TestRPAFailurePath:
    async def test_rpa_submit_then_mark_failed(self, client):
        user_token = await _sms_login(client, "13706060001")
        admin_token = await _admin_login(client)
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)

        # 管理端把订单推到 failed (RPA 系统失败场景)
        r = await _admin_set_status(client, admin_token, order_no, "failed", "RPA 超时")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "failed"

        # failed 是终态
        r2 = await _admin_set_status(client, admin_token, order_no, "reviewing")
        assert r2.status_code in (409, 422)

    async def test_abnormal_path(self, client):
        user_token = await _sms_login(client, "13706060002")
        admin_token = await _admin_login(client)
        dest_id = await _ensure_dest("VN")
        mat_id = await _upload(client, user_token)
        order_no = await _create_order(client, user_token, dest_id, mat_id)

        await _submit_order(client, user_token, order_no)
        await _admin_set_status(client, admin_token, order_no, "reviewing")

        r = await _admin_set_status(client, admin_token, order_no, "abnormal", "系统异常")
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "abnormal"

        # abnormal 也是终态
        r2 = await _admin_set_status(client, admin_token, order_no, "reviewing")
        assert r2.status_code in (409, 422)


# ----------------------------------------------------------------- #
# 7. 用户封禁后无法操作                                              #
# ----------------------------------------------------------------- #
class TestDisabledUserBlock:
    async def test_disabled_user_cannot_create_order(self, client):
        from app.models.user import User

        user_token = await _sms_login(client, "13707070001")
        admin_token = await _admin_login(client)
        dest_id = await _ensure_dest("ID")
        mat_id = await _upload(client, user_token)

        # 封禁该用户
        async with AsyncSessionLocal() as s:
            user = await s.scalar(select(User).where(User.email == "13707070001@test.local"))
            user.status = "disabled"
            await s.commit()

        # 用旧 token 创建订单 —— 应被拦截 (token 合法但用户已禁用)
        r = await client.post(
            "/api/v2/orders",
            json={"destination_id": dest_id, "visa_type": "tourism", "material_ids": [mat_id]},
            headers=_bearer(user_token),
        )
        assert r.status_code in (401, 403), f"禁用用户应被拦截，实际 {r.status_code}: {r.text}"
