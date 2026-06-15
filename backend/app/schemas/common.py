"""Common envelope types — used for ALL responses per V2 §1.5.1."""
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiError(BaseModel):
    """Standard error body — V2 §1.5.1."""

    code: str = Field(description="6-digit error code, e.g. '2003'")
    message: str = Field(description="Human-readable summary")
    data: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel, Generic[T]):
    """Generic envelope: {code, message, data}."""

    code: str = "1000"
    message: str = "OK"
    data: Optional[T] = None


# Aliases for typing
OK = "1000"
