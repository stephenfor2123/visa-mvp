"""I18nOverride — 运营文案覆盖表（V0 §4.4.4）。

优先级高于前端内置 json: 前端启动时先加载内置 i18n, 再用此表覆盖。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class I18nOverride(Base):
    __tablename__ = "i18n_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # 前端内置 json 的原值（方便 diff & 一键恢复）
    original_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    updated_by_admin_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("locale", "key", name="uq_i18n_overrides_locale_key"),
        Index("ix_i18n_overrides_locale", "locale"),
        Index("ix_i18n_overrides_key", "key"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<I18nOverride {self.locale}:{self.key}>"