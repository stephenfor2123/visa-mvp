"""Analytics track request / response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TrackEventRequest(BaseModel):
    event: str = Field(..., min_length=1, max_length=64, description="Canonical event name")
    session_id: Optional[str] = Field(None, max_length=64)
    country_code: Optional[str] = Field(None, max_length=8)
    order_no: Optional[str] = Field(None, max_length=32)
    path: Optional[str] = Field(None, max_length=255)
    props: dict[str, Any] = Field(default_factory=dict)


class TrackEventData(BaseModel):
    event_id: int
    event: str
    tracked_at: datetime
