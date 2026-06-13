"""
Loguru configuration. Single sink per process, used by middleware +
service modules. Never `print()` — see CLAUDE.md / WORKLOG.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.core.config import get_settings


_configured = False


def configure_logging() -> None:
    """Idempotent logger setup. Safe to call from app + tests."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        str(log_dir / "app.log"),
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
        enqueue=True,
    )
    _configured = True


def get_logger():
    """Return the configured loguru logger."""
    if not _configured:
        configure_logging()
    return logger
