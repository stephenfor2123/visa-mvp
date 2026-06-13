"""SMS channel abstraction (V2 §4.1.5).

Public surface used by services:
    get_sms_channel() -> SMSChannel

`SMSChannel` is async even though the Mock implementation is purely
in-memory — that way the production Twilio / Aliyun swap is a drop-in.
"""
from app.services.sms.base import SMSChannel  # noqa: F401
from app.services.sms.factory import get_sms_channel  # noqa: F401
