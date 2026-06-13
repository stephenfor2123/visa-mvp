"""Mock SMS channel — V2 default.

Writes a line to logs/sms.log AND returns the raw code in the response
payload (V2 §4.1.4: "测试模式:任意 6 位数字通过" + dev-mode echo).

Production swap: implement TwilioSMSChannel / AliyunSMSChannel in
their own modules and switch via the SMS_CHANNEL env var.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app.services.sms.base import SMSChannel


class MockSMSChannel(SMSChannel):
    """In-process mock — no external dependencies, ideal for dev/test."""

    def __init__(self, log_dir: str | None = None) -> None:
        self._log_dir = Path(log_dir) if log_dir else None
        if self._log_dir:
            self._log_dir.mkdir(parents=True, exist_ok=True)
        self._sms_log = logger.bind(component="sms_mock")

    async def send_code(
        self, phone: str, phone_country: str, code: str, purpose: str
    ) -> dict[str, Any]:
        ts = datetime.now().isoformat(timespec="seconds")
        line = (
            f"{ts} [SMS-MOCK] phone={phone_country}{phone} "
            f"code={code} purpose={purpose}"
        )
        # 1. structured log via loguru
        self._sms_log.info(line)

        # 2. also append to logs/sms.log (V2 §4.1.4 says backend writes a line
        #    there; downstream tools (frontend dev mode / admin) tail it).
        if self._log_dir:
            try:
                (self._log_dir / "sms.log").open("a", encoding="utf-8").write(
                    line + "\n"
                )
            except OSError as exc:  # pragma: no cover - very rare
                self._sms_log.warning(f"failed to append sms.log: {exc}")

        return {
            "ok": True,
            "channel_txn_id": f"mock_{int(time.time() * 1000)}",
            "error": None,
        }
