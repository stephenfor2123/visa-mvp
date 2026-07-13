"""Admin permission registry — single source of truth for all perm codes.

定义规则:
- 任何新增 perm 必须在此处声明,前端通过 /admin/permissions 接口拉取,
  不允许在前端硬编码 perm 字符串。
- perm code 用 `domain.action` 形式 (e.g. order.edit_status), 与 i18n key
  `admin.perms.<code>` 一一对应。

历史兼容 (W34 6 个顶层 perm):
- dashboard / orders / payments / users / countries / settings 这 6 个
  老 perm code 保留,作为"侧边栏菜单可见性"的判据(粗粒度)。
- 新 perm code (e.g. order.view) 用于接口级鉴权(细粒度)。
- super_admin 自动拥有所有 perm, 不需要列举。
"""
from __future__ import annotations

from typing import Final


# 全部 perm code 常量
# 格式: {code, label_key}
# - code: 用于后端鉴权 / 角色 permissions JSON
# - label_key: 前端 i18n key (admin.perms.<code>),前端展示用

PERMISSIONS: Final[list[dict[str, str]]] = [
    # ---- 顶层菜单 (W34 兼容, 旧 staff 角色还依赖这些) ----
    {"code": "dashboard", "label_key": "admin.perms.dashboard",
     "group": "menu", "description": "总览看板"},
    {"code": "orders", "label_key": "admin.perms.orders",
     "group": "menu", "description": "订单管理菜单"},
    {"code": "payments", "label_key": "admin.perms.payments",
     "group": "menu", "description": "支付流水菜单"},
    {"code": "users", "label_key": "admin.perms.users",
     "group": "menu", "description": "用户管理菜单"},
    {"code": "countries", "label_key": "admin.perms.countries",
     "group": "menu", "description": "国家配置菜单"},
    {"code": "settings", "label_key": "admin.perms.settings",
     "group": "menu", "description": "系统设置菜单"},

    # ---- 订单细粒度 ----
    {"code": "order.view", "label_key": "admin.perms.order.view",
     "group": "order", "description": "查看订单列表/详情"},
    {"code": "order.edit_status", "label_key": "admin.perms.order.edit_status",
     "group": "order", "description": "审核订单状态(approved/rejected)"},
    {"code": "order.close", "label_key": "admin.perms.order.close",
     "group": "order", "description": "关闭订单(abnormal/failed/closed)"},
    {"code": "order.edit_field", "label_key": "admin.perms.order.edit_field",
     "group": "order", "description": "修改订单金额/材料/申请人资料"},
    {"code": "order.rerun_rpa", "label_key": "admin.perms.order.rerun_rpa",
     "group": "order", "description": "重派 RPA 任务"},
    {"code": "order.export", "label_key": "admin.perms.order.export",
     "group": "order", "description": "导出订单数据"},

    # ---- 支付 ----
    {"code": "payment.view", "label_key": "admin.perms.payment.view",
     "group": "payment", "description": "查看支付流水"},
    {"code": "payment.refund", "label_key": "admin.perms.payment.refund",
     "group": "payment", "description": "退款操作"},

    # ---- 用户 ----
    {"code": "user.view", "label_key": "admin.perms.user.view",
     "group": "user", "description": "查看 C 端用户"},
    {"code": "user.edit", "label_key": "admin.perms.user.edit",
     "group": "user", "description": "修改 C 端用户资料"},
    {"code": "user.disable", "label_key": "admin.perms.user.disable",
     "group": "user", "description": "禁用/恢复账号"},
    {"code": "user.reset_password", "label_key": "admin.perms.user.reset_password",
     "group": "user", "description": "重置密码"},

    # ---- 看板 ----
    {"code": "dashboard.view", "label_key": "admin.perms.dashboard.view",
     "group": "dashboard", "description": "查看运营看板"},
    {"code": "dashboard.export", "label_key": "admin.perms.dashboard.export",
     "group": "dashboard", "description": "导出看板报表"},

    # ---- 系统配置 ----
    {"code": "country.manage", "label_key": "admin.perms.country.manage",
     "group": "system", "description": "签证国家 CRUD"},
    {"code": "rag.review", "label_key": "admin.perms.rag.review",
     "group": "system", "description": "RAG 审核"},
    {"code": "ai_rules.edit", "label_key": "admin.perms.ai_rules.edit",
     "group": "system", "description": "AI 校验规则编辑"},
    {"code": "role.manage", "label_key": "admin.perms.role.manage",
     "group": "system", "description": "角色与管理员账号管理"},
    {"code": "pricing.manage", "label_key": "admin.perms.pricing.manage",
     "group": "system", "description": "平台服务费与促销定价"},
    {"code": "system.cleanup", "label_key": "admin.perms.system.cleanup",
     "group": "system", "description": "数据清理"},
]


# 分组元数据,前端 perm grid 分组渲染用
PERM_GROUPS: Final[dict[str, str]] = {
    "menu": "menu",
    "order": "order",
    "payment": "payment",
    "user": "user",
    "dashboard": "dashboard",
    "system": "system",
}


# 6 个内置角色权限矩阵
ROLE_PERMISSIONS: Final[dict[str, dict[str, list[str]]] | dict[str, list[str]]] = {
    # 超级管理员 — 拥有全部 perm
    "super_admin": {
        "name": "超级管理员",
        "description": "拥有系统全部权限",
        "permissions": [p["code"] for p in PERMISSIONS],
    },
    # 运营主管
    "ops_manager": {
        "name": "运营主管",
        "description": "全面订单操作 + 用户/材料 + 数据导出",
        "permissions": [
            "dashboard", "orders", "payments", "users",
            "order.view", "order.edit_status", "order.close", "order.export",
            "payment.view",
            "user.view", "user.edit", "user.disable", "user.reset_password",
            "dashboard.view", "dashboard.export",
            "settings", "pricing.manage",
            "rag.review",
        ],
    },
    # 初审专员
    "reviewer": {
        "name": "初审专员",
        "description": "审核订单状态、查看详情",
        "permissions": [
            "dashboard", "orders",
            "order.view", "order.edit_status",
            "user.view",
            "dashboard.view",
        ],
    },
    # 财务专员
    "finance": {
        "name": "财务专员",
        "description": "订单 + 支付流水 + 数据导出",
        "permissions": [
            "dashboard", "orders", "payments",
            "order.view", "order.export",
            "payment.view", "payment.refund",
            "dashboard.view", "dashboard.export",
        ],
    },
    # 客服
    "support": {
        "name": "客服",
        "description": "只读订单(脱敏) + 用户查询",
        "permissions": [
            "dashboard", "orders",
            "order.view",
            "user.view",
            "dashboard.view",
        ],
    },
    # 数据分析
    "data_analyst": {
        "name": "数据分析",
        "description": "Dashboard + 数据导出",
        "permissions": [
            "dashboard",
            "dashboard.view", "dashboard.export",
            "order.export",
        ],
    },
}


def all_perm_codes() -> list[str]:
    """返回全部 perm code 列表(用于参数校验 / API 响应)"""
    return [p["code"] for p in PERMISSIONS]


def perm_exists(code: str) -> bool:
    """判断 perm code 是否在注册表中(创建角色时拒绝未知 code)"""
    return code in all_perm_codes()