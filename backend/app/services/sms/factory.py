"""Channel factory — single source of truth for which channel to use."""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.sms.base import SMSChannel
from app.services.sms.mock import MockSMSChannel
from app.services.sms.twilio import TwilioSMSChannel


@lru_cache(maxsize=1)
def get_sms_channel() -> SMSChannel:
    """Pick the channel configured in env (default: mock)."""
    code = get_settings().sms_channel.lower()
    if code == "mock":
        return MockSMSChannel(log_dir=get_settings().sms_log_dir)
    if code == "twilio":
        return TwilioSMSChannel()
    # aliyun / unknown — fall back to mock so dev never breaks.
    return MockSMSChannel(log_dir=get_settings().sms_log_dir)
