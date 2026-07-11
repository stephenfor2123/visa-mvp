"""AdminUser model — 后台管理员用户，与 C-user 完全独立（W34 权限系统）。"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import relationship

from app.core.db import Base


class AdminUser(Base):
    """后台管理员账号（独立于 C-user 体系）。

    登录方式：username + password_hash（与 ADMIN_PASSWORD env var 并行，
    DB 中的账号优先级更高，支持多账号管理）。
    """
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True, comment="登录账号")
    password_hash = Column(String(256), nullable=False, comment="bcrypt 哈希后的密码")
    role_id = Column(Integer, ForeignKey("admin_roles.id"), nullable=False, comment="关联角色")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")

    # W46 fix: list_admin_users 在 service 用 selectinload(AdminUser.role),
    # 模型侧必须显式声明 relationship 否则 selectinload 抛 AttributeError。
    role = relationship("AdminRole", lazy="joined")