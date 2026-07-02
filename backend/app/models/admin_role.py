"""AdminRole model — 后台角色定义（W34 权限系统）。"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, JSON, Boolean

from app.core.db import Base


class AdminRole(Base):
    """后台角色。

    - super_admin: 超级管理员，拥有所有权限
    - staff: 普通员工，权限由 permissions 数组控制
    """
    __tablename__ = "admin_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False, comment="角色名称")
    code = Column(String(32), unique=True, nullable=False, comment="角色代码")
    permissions = Column(JSON, nullable=False, default=list, comment="权限码列表")
    description = Column(String(256), nullable=True, comment="角色描述")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)