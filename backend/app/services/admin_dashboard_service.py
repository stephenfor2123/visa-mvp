"""AdminDashboardService — V2 dashboard 5 个新接口的业务实现 (W37).

跟 AdminService 解耦, 单文件 ~370 行, 复用 AdminService 已有的 ORM imports
来维持事务/类型一致性 (这俩 service 都接 AsyncSession, 共享 model).

接口清单 (前端 /admin/dashboard 用):
  - get_summary()             → 4 张 KPI 卡 + 与上周同期对比
  - get_trend(metric, range)  → N 天每日序列 (orders / revenue / users)
  - get_funnel(range)         → 支付优先漏斗 (下单 → 支付页 → 支付成功 → 履约)
  - get_top_countries(range)  → 按 destination_id 分组 + join Destination
  - get_alerts()              → 规则驱动, 命中即入列, 不达阈值不出

时间窗全 UTC, 跟 Order.created_at server_default UTC 一致.
汇率暂不处理非 USD 币种 — total_amount 已经是 USD.

Caches: 60s in-memory TTL via instance attr; 对象生命 = uvicorn worker 生命.
        刷新意味着 60s 后下次请求重算. 对 PM/admin 仪表盘足够, 不需要 Redis.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.destination import VisaDestination
from app.models.order import Order
from app.models.user import User


_RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _pct_change(curr: float, prev: float):
    """涨跌幅百分比 (0.12 = +12%, -0.05 = -5%).

    W63: prev=0 时不要假装 +100%,返 None 让前端走"新"分支。
    - prev=0, curr=0: 无变化 → 0.0
    - prev=0, curr>0: 无对比基线 → None (前端不显箭头,显"新")
    - prev>0: 正常算 (curr-prev)/prev
    """
    if prev == 0:
        return None if curr > 0 else 0.0
    return round((curr - prev) / prev, 4)


class AdminDashboardService:
    """Dashboard 业务类. 持有 db 句柄, 5 个方法相互独立, 可并行调用."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # helpers                                                              #
    # ------------------------------------------------------------------ #
    async def _qcount(self, q) -> int:
        """SELECT COUNT(*) helper — 0 when no rows."""
        return int((await self.db.execute(q)).scalar() or 0)

    # ------------------------------------------------------------------ #
    # summary (4 张 KPI 大卡 + 同期对比)                                   #
    # ------------------------------------------------------------------ #
    async def get_summary(self) -> dict[str, Any]:
        """顶部 4 张 KPI: 今日订单/今日营收/今日新用户/今日成功率, + 与上周同日对比."""
        cache_key = "_summary_cache"
        cached = getattr(self, cache_key, None)
        now = datetime.utcnow()
        if cached and cached.get("_ts", 0) + 60 > now.timestamp():
            out = dict(cached)
            out["generated_at"] = now
            out["cached"] = True
            return out

        today_0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_0.replace(day=1)

        # 上周同日窗口 (昨天 → 当天的一个相对天) — 取同日作为同比
        week_window_start = today_0 - timedelta(days=7)
        week_window_end = today_0

        # 今日订单数
        today_orders = await self._qcount(
            select(func.count()).select_from(Order).where(Order.created_at >= today_0)
        )

        # 今日营收 (submitted_at 非空, 表示已支付的订单)
        today_revenue = float(
            (await self.db.execute(
                select(func.coalesce(func.sum(Order.total_amount), 0))
                .select_from(Order)
                .where(Order.created_at >= today_0, Order.submitted_at.isnot(None))
            )).scalar() or 0
        )

        # 今日新用户
        today_new_users = await self._qcount(
            select(func.count()).select_from(User).where(User.created_at >= today_0)
        )

        # 今日成功率
        if today_orders > 0:
            today_paid = await self._qcount(
                select(func.count()).select_from(Order)
                .where(Order.created_at >= today_0, Order.submitted_at.isnot(None))
            )
            today_success = round(today_paid / today_orders, 4)
        else:
            today_success = 0.0

        # 上周同日窗口
        last_orders = await self._qcount(
            select(func.count()).select_from(Order).where(
                Order.created_at >= week_window_start,
                Order.created_at < week_window_end,
            )
        )
        last_revenue = float(
            (await self.db.execute(
                select(func.coalesce(func.sum(Order.total_amount), 0))
                .select_from(Order)
                .where(
                    Order.created_at >= week_window_start,
                    Order.created_at < week_window_end,
                    Order.submitted_at.isnot(None),
                )
            )).scalar() or 0
        )
        last_users = await self._qcount(
            select(func.count()).select_from(User).where(
                User.created_at >= week_window_start,
                User.created_at < week_window_end,
            )
        )

        # 本月 + 待处理 + 总用户
        month_orders = await self._qcount(
            select(func.count()).select_from(Order).where(Order.created_at >= month_start)
        )
        pending_orders = await self._qcount(
            select(func.count()).select_from(Order).where(
                Order.status.in_(("created", "submitted", "reviewing"))
            )
        )
        total_users = await self._qcount(select(func.count()).select_from(User))

        out = {
            "today_orders": today_orders,
            "today_revenue_usd": round(today_revenue, 2),
            "today_new_users": today_new_users,
            "today_success_rate": today_success,
            "delta_orders_pct": _pct_change(today_orders, last_orders),
            "delta_revenue_pct": _pct_change(today_revenue, last_revenue),
            "delta_users_pct": _pct_change(today_new_users, last_users),
            "month_orders": month_orders,
            "total_users": total_users,
            "pending_orders": pending_orders,
            "generated_at": now,
            "cached": False,
        }
        cache_blob = dict(out)
        cache_blob["_ts"] = now.timestamp()
        setattr(self, cache_key, cache_blob)
        return out

    # ------------------------------------------------------------------ #
    # trend                                                                #
    # ------------------------------------------------------------------ #
    async def get_trend(self, metric: str = "orders", range_key: str = "7d") -> dict[str, Any]:
        """N 天 (默认 7) 每日 3 个指标的序列化. 只算 metric 当前指向的曲线, 另两个在 total_* 里."""
        days = _RANGE_DAYS.get(range_key, 7)
        now = datetime.utcnow()
        today_0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = today_0 - timedelta(days=days - 1)

        # orders + revenue 一次性聚合
        orders_q = (
            select(
                func.date(Order.created_at).label("d"),
                func.count(Order.id).label("c"),
                func.coalesce(func.sum(Order.total_amount), 0).label("rev"),
            )
            .where(Order.created_at >= start)
            .group_by(func.date(Order.created_at))
        )
        orders_rows = (await self.db.execute(orders_q)).all()
        orders_map = {str(r.d): int(r.c) for r in orders_rows}
        revenue_map = {str(r.d): float(r.rev or 0) for r in orders_rows}

        users_q = (
            select(func.date(User.created_at).label("d"), func.count(User.id).label("c"))
            .where(User.created_at >= start)
            .group_by(func.date(User.created_at))
        )
        users_rows = (await self.db.execute(users_q)).all()
        users_map = {str(r.d): int(r.c) for r in users_rows}

        points = []
        total_orders = 0
        total_revenue = 0.0
        total_users = 0
        for i in range(days):
            day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            orders = orders_map.get(day, 0)
            revenue = revenue_map.get(day, 0.0)
            users = users_map.get(day, 0)
            total_orders += orders
            total_revenue += revenue
            total_users += users
            points.append({
                "date": day,
                "orders": orders,
                "revenue_usd": round(revenue, 2),
                "new_users": users,
            })

        return {
            "metric": metric,
            "range": range_key,
            "points": points,
            "total_orders": total_orders,
            "total_revenue_usd": round(total_revenue, 2),
            "total_new_users": total_users,
            "generated_at": now,
        }

    # ------------------------------------------------------------------ #
    # funnel                                                               #
    # ------------------------------------------------------------------ #
    async def get_funnel(self, range_key: str = "7d") -> dict[str, Any]:
        """Pay-first funnel: order_create → checkout → paid → completed.

        Early client steps (country_selected / wizard_started) are prepended
        when analytics_events has data in the window.
        """
        from app.models.analytics_event import AnalyticsEvent
        from app.services.analytics import (
            EVENT_CHECKOUT_VIEWED,
            EVENT_COUNTRY_SELECTED,
            EVENT_WIZARD_STARTED,
        )

        days = _RANGE_DAYS.get(range_key, 7)
        now = datetime.utcnow()
        start = now - timedelta(days=days)

        async def _event_count(name: str) -> int:
            return await self._qcount(
                select(func.count()).select_from(AnalyticsEvent).where(
                    AnalyticsEvent.event_name == name,
                    AnalyticsEvent.created_at >= start,
                )
            )

        country_selected = await _event_count(EVENT_COUNTRY_SELECTED)
        wizard_started = await _event_count(EVENT_WIZARD_STARTED)

        # 1) 创建订单
        create = await self._qcount(
            select(func.count()).select_from(Order).where(Order.created_at >= start)
        )
        if create == 0:
            create = await self._qcount(
                select(func.count()).select_from(AuditLog).where(
                    AuditLog.action == "order.create",
                    AuditLog.created_at >= start,
                )
            )

        # 2) 进入支付页 (client checkout_viewed)
        checkout = await _event_count(EVENT_CHECKOUT_VIEWED)

        # 3) 支付成功 — paid / submitted(legacy) / paid_at / submitted_at
        paid = await self._qcount(
            select(func.count()).select_from(Order).where(
                Order.created_at >= start,
                or_(
                    Order.status.in_(
                        ("paid", "completed", "submitted", "reviewing", "approved", "closed")
                    ),
                    Order.paid_at.isnot(None),
                    Order.submitted_at.isnot(None),
                ),
            )
        )

        # 4) 履约完成
        finish = await self._qcount(
            select(func.count()).select_from(Order).where(
                Order.created_at >= start,
                Order.status.in_(("completed", "approved", "closed")),
            )
        )

        steps: list[dict[str, Any]] = []
        # Prepend acquisition steps only when we have client telemetry
        if country_selected > 0 or wizard_started > 0:
            if country_selected > 0:
                steps.append({
                    "key": "country_selected",
                    "label": "选国家",
                    "count": country_selected,
                })
            if wizard_started > 0:
                steps.append({
                    "key": "wizard_started",
                    "label": "进入向导",
                    "count": wizard_started,
                })

        steps.extend([
            {"key": "order_create", "label": "创建订单", "count": create},
            {"key": "checkout_viewed", "label": "进入支付页", "count": checkout},
            {"key": "payment_success", "label": "支付成功", "count": paid},
            {"key": "order_completed", "label": "履约完成", "count": finish},
        ])

        for i, s in enumerate(steps):
            if i == 0:
                s["conversion_pct"] = 100.0
            else:
                prev = steps[i - 1]["count"]
                raw_pct = round((s["count"] / prev * 100.0), 2) if prev > 0 else 0.0
                s["conversion_pct"] = min(100.0, raw_pct)

        # Overall: first money-relevant step → finish (order_create → completed)
        overall = min(100.0, round((finish / create * 100.0), 2)) if create > 0 else 0.0

        return {
            "range": range_key,
            "steps": steps,
            "overall_conversion_pct": overall,
            "generated_at": now,
        }

    # ------------------------------------------------------------------ #
    # top countries                                                        #
    # ------------------------------------------------------------------ #
    async def get_top_countries(
        self, range_key: str = "7d", limit: int = 10
    ) -> dict[str, Any]:
        """按 destination_id 分组聚合订单量+营收, join Destination 拿 country_code + 中文名."""
        days = _RANGE_DAYS.get(range_key, 7)
        now = datetime.utcnow()
        start = now - timedelta(days=days)

        rows = (
            await self.db.execute(
                select(
                    Order.destination_id,
                    func.count(Order.id).label("c"),
                    func.coalesce(func.sum(Order.total_amount), 0).label("rev"),
                )
                .where(Order.created_at >= start)
                .group_by(Order.destination_id)
                .order_by(func.count(Order.id).desc())
                .limit(limit)
            )
        ).all()

        if not rows:
            return {"range": range_key, "items": [], "generated_at": now}

        dest_ids = [r.destination_id for r in rows]
        dest_rows = (
            await self.db.execute(
                select(VisaDestination).where(VisaDestination.id.in_(dest_ids))
            )
        ).scalars().all()
        dest_map = {d.id: d for d in dest_rows}

        total = await self._qcount(
            select(func.count()).select_from(Order).where(Order.created_at >= start)
        )

        items = []
        for r in rows:
            d = dest_map.get(r.destination_id)
            country_code = (d.country_code if d else None) or "--"
            country_name = country_code
            if d and d.country_name_i18n:
                try:
                    i18n = json.loads(d.country_name_i18n)
                    country_name = (
                        i18n.get("zh-CN") or i18n.get("zh") or i18n.get("en")
                        or country_code
                    )
                except Exception:
                    country_name = country_code
            items.append({
                "destination_id": r.destination_id,
                "country_code": country_code,
                "country_name": country_name,
                "order_count": int(r.c),
                "revenue_usd": round(float(r.rev or 0), 2),
                "conversion_pct": round(int(r.c) / total * 100.0, 2) if total else 0.0,
            })

        return {
            "range": range_key,
            "items": items,
            "generated_at": now,
        }

    # ------------------------------------------------------------------ #
    # alerts                                                               #
    # ------------------------------------------------------------------ #
    async def get_alerts(self) -> dict[str, Any]:
        """规则式告警: 每条独立判断, 不达阈值不出; 命中即入列. 60s cache."""
        cache_key = "_alerts_cache"
        cached = getattr(self, cache_key, None)
        now = datetime.utcnow()
        if cached and cached.get("_ts", 0) + 60 > now.timestamp():
            out = {k: v for k, v in cached.items() if k != "_ts"}
            out["generated_at"] = now
            return out

        items = []

        # 1) 待处理订单 > 30 (积压)
        pending_count = await self._qcount(
            select(func.count()).select_from(Order).where(
                Order.status.in_(("created", "submitted"))
            )
        )
        if pending_count > 30:
            items.append({
                "severity": "warning",
                "code": "pending_orders_high",
                "title": f"待处理订单积压 ({pending_count})",
                "detail": "待处理订单超过 30, 建议检查 RPA 队列与人工坐席",
                "metric_value": pending_count,
                "threshold": 30.0,
            })

        # 2) enabled 国家 24h 零订单
        zero_since = now - timedelta(hours=24)
        active_dests = (
            await self.db.execute(
                select(VisaDestination).where(VisaDestination.enabled == True)  # noqa: E712
            )
        ).scalars().all()
        if active_dests:
            recent_order_counts = (
                await self.db.execute(
                    select(
                        Order.destination_id,
                        func.count(Order.id).label("c"),
                    )
                    .where(Order.created_at >= zero_since)
                    .group_by(Order.destination_id)
                )
            ).all()
            recent_map = {r.destination_id: int(r.c) for r in recent_order_counts}
            zero_dests = [
                d for d in active_dests
                if recent_map.get(d.id, 0) == 0 and (d.country_code or "")
            ]
            if zero_dests:
                names = ", ".join(d.country_code for d in zero_dests[:5])
                more = len(zero_dests) - 5
                suffix = f" 等 {more} 个" if more > 0 else ""
                items.append({
                    "severity": "info",
                    "code": "zero_order_country",
                    "title": f"{len(zero_dests)} 个启用的目的地 24h 零订单",
                    "detail": f"{names}{suffix} 过去 24 小时没有任何新订单",
                    "metric_value": float(len(zero_dests)),
                    "threshold": 0.0,
                })

        # 3) 失败/异常订单 24h > 10
        fail_count = await self._qcount(
            select(func.count()).select_from(Order).where(
                Order.created_at >= zero_since,
                Order.status.in_(("failed", "abnormal")),
            )
        )
        if fail_count > 10:
            items.append({
                "severity": "critical",
                "code": "rpa_failure_spike",
                "title": f"近 24h 失败/异常订单 {fail_count} 单",
                "detail": "正常值应 < 5, 请检查 RPA 调度与目标站点可用性",
                "metric_value": float(fail_count),
                "threshold": 10.0,
            })

        # 4) 总体支付成功率过低 (< 30%)
        total_orders = await self._qcount(select(func.count()).select_from(Order))
        if total_orders > 0:
            paid_orders = await self._qcount(
                select(func.count()).select_from(Order).where(Order.submitted_at.isnot(None))
            )
            overall_rate = paid_orders / total_orders
            if overall_rate < 0.3:
                items.append({
                    "severity": "warning",
                    "code": "payment_success_low",
                    "title": f"整体支付成功率 {overall_rate*100:.1f}%",
                    "detail": "历史支付成功率低于 30%, 可能影响营收, 建议排查支付链路",
                    "metric_value": round(overall_rate * 100, 2),
                    "threshold": 30.0,
                })

        out = {"items": items, "generated_at": now}
        cache_blob = dict(out)
        cache_blob["generated_at"] = now
        cache_blob["_ts"] = now.timestamp()
        setattr(self, cache_key, cache_blob)
        return out
