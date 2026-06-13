"""Abstract base for SMS channels — V2 §4.1.5."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

Purpose = Literal["register", "login", "reset", "destroy"]


class SMSChannel(ABC):
    """All concrete channels must implement `send_code`."""

    @abstractmethod
    async def send_code(
        self, phone: str, phone_country: str, code: str, purpose: Purpose
    ) -> dict:
        """Send a 6-digit OTP.

        Returns a dict:
            {
              "ok": bool,
              "channel_txn_id": str,   # unique id for this send (mock_xxx / tw_xxx)
              "error": str | None,     # present only when ok is False
            }
        """
        raise NotImplementedError
