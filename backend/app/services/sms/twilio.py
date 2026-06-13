"""Twilio SMS channel — V3+ placeholder (V2 §4.1.5).

NOT IMPLEMENTED in W1. Exists so that future code can `import` it and
the factory can be configured without import-time errors.
"""
from __future__ import annotations

from typing import Any

from app.services.sms.base import SMSChannel


class TwilioSMSChannel(SMSChannel):
    async def send_code(
        self, phone: str, phone_country: str, code: str, purpose: str
    ) -> dict[str, Any]:
        raise NotImplementedError("TwilioSMSChannel ships in V3+")
