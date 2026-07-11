"""Email change flow schemas — W1.

User requests email change with a new email. Backend issues a verification
token (signed JWT, 30 min TTL) and emails the link to the new address. User
clicks the link (or frontend calls the confirm endpoint with the token) to
complete the change.

A separate "email_change_request" model is not needed — the token is the
state. The user.email_pending field on the User row holds the new email
between request and confirm.
"""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class EmailChangeRequest(BaseModel):
    """Body for POST /profile/email/change-request."""
    new_email: EmailStr = Field(..., description="The new email address to migrate to")
    password: str = Field(..., min_length=1, description="Current account password (re-auth)")


class EmailChangeConfirm(BaseModel):
    """Body for POST /profile/email/change-confirm."""
    token: str = Field(..., min_length=8, description="Token from the verification email link")


class EmailChangeResponse(BaseModel):
    """Response on request or confirm."""
    message: str
    pending_email: str | None = None
