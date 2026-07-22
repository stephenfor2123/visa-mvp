"""
/api/v2/profile/* — Personal profile management (W1).

Endpoints
---------
Account
  GET    /profile                      — current user summary (id, email, status, created_at, language_pref)
Applicant library
  GET    /profile/applicants           — list all applicants for current user
  POST   /profile/applicants           — add a new applicant (surname, given_name, passport_no)
  PATCH  /profile/applicants/{id}      — edit an existing applicant
  DELETE /profile/applicants/{id}      — remove an applicant
Email change
  POST   /profile/email/change-request — start an email change (re-auth + new email)
  POST   /profile/email/change-confirm — confirm with token from the verification email
  POST   /profile/email/change-cancel  — cancel a pending change

Why this lives under /profile (not /applicants):
- The whole point is "personal info management" — applicants and email
  changes are both part of that. Keeping them under one router prefix
  makes the front-end easier to wire (one base path) and aligns with
  the future /profile/{w2 things like MFA, sessions, etc.}.

Hard rules
----------
- All endpoints require a valid access token.
- Applicants are scoped to current_user.id. No cross-user visibility.
- Email change requires password re-auth + token verification on the new
  address — never trust the user-side request alone.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Path, Request
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user, verify_password
from app.models.applicant import Applicant
from app.models.user import User
from app.schemas.applicant import (
    ApplicantCreate,
    ApplicantCreateResponse,
    ApplicantItem,
    ApplicantListResponse,
    ApplicantUpdate,
)
from app.schemas.common import ApiResponse
from app.schemas.email_change import (
    EmailChangeConfirm,
    EmailChangeRequest,
    EmailChangeResponse,
)
from app.services.email_service import (
    EmailChangeVerification,
    send_email_change_verification,
)


class AccountDeleteRequest(BaseModel):
    """Self-service account deletion.

    Password users must re-auth with password. Google/WeChat-only accounts
    may omit password and set `confirm=True` (plus optional confirmation_code
    when email confirmation is required later).
    """
    model_config = ConfigDict(extra="forbid")

    password: Optional[str] = Field(None, min_length=1, max_length=128)
    confirm: bool = Field(..., description="Must be true to proceed")
    confirmation_code: Optional[str] = Field(
        None, max_length=32, description="Optional email confirmation code for OAuth-only accounts"
    )


class ConsentGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(..., min_length=1, max_length=64)
    version: str = Field("v1", max_length=32)


class ConsentRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(..., min_length=1, max_length=64)
    version: str = Field("v1", max_length=32)


class ProcessingRestrictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    restricted: bool = Field(..., description="True = Art.18/21 restrict new processing")


router = APIRouter(prefix="/profile", tags=["profile"])
_log = get_logger()

# W1 cap — one account can have at most this many applicants.
APPLICANT_LIMIT_PER_USER = 10


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _smart_join_name(surname: str, given_name: str) -> str:
    """If surname is ASCII letters, separate with a space; else concatenate.

    Mirrors /my/applicants._display_name for visual consistency across the
    product (header dropdown vs. profile page).
    """
    s = (surname or "").strip()
    g = (given_name or "").strip()
    if s and all(ord(c) < 128 for c in s if c.isalpha()):
        return f"{s} {g}".strip()
    return f"{s}{g}"


def _applicant_to_item(a: Applicant) -> ApplicantItem:
    return ApplicantItem(
        id=a.id,
        surname=a.surname,
        given_name=a.given_name,
        display_name=_smart_join_name(a.surname, a.given_name),
        passport_no=a.passport_no,
        is_minor=bool(getattr(a, "is_minor", False)),
        guardian_relationship=getattr(a, "guardian_relationship", None),
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


async def _check_user_limit(db: AsyncSession, user_id: int) -> None:
    """Raise APPLICANT_LIMIT_REACHED if user is at the cap."""
    stmt = select(Applicant).where(Applicant.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()
    if len(rows) >= APPLICANT_LIMIT_PER_USER:
        raise BizException(
            ErrorCode.APPLICANT_LIMIT_REACHED,
            message=f"Applicant limit reached ({APPLICANT_LIMIT_PER_USER} per user)",
        )


async def _get_owned_applicant(
    db: AsyncSession, applicant_id: int, user_id: int
) -> Applicant:
    """Fetch an applicant and ensure it belongs to the current user."""
    a = await db.get(Applicant, applicant_id)
    if a is None or a.user_id != user_id:
        raise BizException(
            ErrorCode.APPLICANT_NOT_FOUND, message="Applicant not found"
        )
    return a


# --------------------------------------------------------------------------- #
# GET /profile                                                                #
# --------------------------------------------------------------------------- #
@router.get(
    "",
    response_model=ApiResponse[dict],
    summary="Current user summary (id, email, status, created_at, language_pref, email_pending)",
)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={
            "id": current_user.id,
            "email": current_user.email,
            "email_pending": current_user.email_pending,
            "username": current_user.username,
            "nickname": current_user.nickname,
            "status": current_user.status,
            "language_pref": current_user.language_pref,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "applicant_limit": APPLICANT_LIMIT_PER_USER,
            "processing_restricted": bool(getattr(current_user, "processing_restricted", False)),
            "has_password": bool(current_user.password_hash),
            "privacy_support_email": get_settings().privacy_support_email,
        },
    )


# --------------------------------------------------------------------------- #
# GET /profile/applicants                                                     #
# --------------------------------------------------------------------------- #
@router.get(
    "/applicants",
    response_model=ApiResponse[ApplicantListResponse],
    summary="List all applicants for current user",
)
async def list_applicants(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ApplicantListResponse]:
    stmt = (
        select(Applicant)
        .where(Applicant.user_id == current_user.id)
        .order_by(Applicant.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [_applicant_to_item(a) for a in rows]
    return ApiResponse[ApplicantListResponse](
        code="1000",
        message="OK",
        data=ApplicantListResponse(items=items, total=len(items)),
    )


# --------------------------------------------------------------------------- #
# POST /profile/applicants                                                    #
# --------------------------------------------------------------------------- #
@router.post(
    "/applicants",
    response_model=ApiResponse[ApplicantCreateResponse],
    status_code=201,
    summary="Add a new applicant",
)
async def create_applicant(
    body: ApplicantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ApplicantCreateResponse]:
    await _check_user_limit(db, current_user.id)

    # Pre-check for friendlier errors (and to avoid the IntegrityError
    # greenlet-spawn dance when running on async SQLAlchemy).
    existing_name = await db.execute(
        select(Applicant).where(
            Applicant.user_id == current_user.id,
            Applicant.surname == body.surname,
            Applicant.given_name == body.given_name,
        )
    )
    if existing_name.scalars().first():
        raise BizException(
            ErrorCode.APPLICANT_DUPLICATE_NAME,
            message="An applicant with the same name already exists in your account",
        )

    existing_pp = await db.execute(
        select(Applicant).where(Applicant.passport_no == body.passport_no)
    )
    if existing_pp.scalars().first():
        raise BizException(
            ErrorCode.APPLICANT_DUPLICATE_PASSPORT,
            message="This passport number is already linked to another applicant",
        )

    new_app = Applicant(
        user_id=current_user.id,
        surname=body.surname,
        given_name=body.given_name,
        passport_no=body.passport_no,
        is_minor=bool(body.is_minor),
        guardian_relationship=body.guardian_relationship if body.is_minor else None,
    )
    db.add(new_app)
    await db.commit()
    await db.refresh(new_app)
    _log.info(
        "profile.applicant.create",
        extra={
            "user_id": current_user.id,
            "event_type": "profile.applicant.create",
            "applicant_id": new_app.id,
            "status": "success",
        },
    )
    return ApiResponse[ApplicantCreateResponse](
        code="1000",
        message="OK",
        data=ApplicantCreateResponse(applicant=_applicant_to_item(new_app)),
    )


# --------------------------------------------------------------------------- #
# PATCH /profile/applicants/{id}                                              #
# --------------------------------------------------------------------------- #
@router.patch(
    "/applicants/{applicant_id}",
    response_model=ApiResponse[ApplicantCreateResponse],
    summary="Edit an existing applicant",
)
async def update_applicant(
    body: ApplicantUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    applicant_id: int = Path(..., ge=1),
) -> ApiResponse[ApplicantCreateResponse]:
    a = await _get_owned_applicant(db, applicant_id, current_user.id)

    new_surname = body.surname if body.surname is not None else a.surname
    new_given = body.given_name if body.given_name is not None else a.given_name
    new_pp = body.passport_no if body.passport_no is not None else a.passport_no

    # Pre-check: would this update collide with another row?
    if (new_surname, new_given) != (a.surname, a.given_name):
        existing_name = await db.execute(
            select(Applicant).where(
                Applicant.user_id == current_user.id,
                Applicant.surname == new_surname,
                Applicant.given_name == new_given,
                Applicant.id != a.id,
            )
        )
        if existing_name.scalars().first():
            raise BizException(
                ErrorCode.APPLICANT_DUPLICATE_NAME,
                message="An applicant with the same name already exists in your account",
            )

    if new_pp != a.passport_no:
        existing_pp = await db.execute(
            select(Applicant).where(
                Applicant.passport_no == new_pp,
                Applicant.id != a.id,
            )
        )
        if existing_pp.scalars().first():
            raise BizException(
                ErrorCode.APPLICANT_DUPLICATE_PASSPORT,
                message="This passport number is already linked to another applicant",
            )

    a.surname = new_surname
    a.given_name = new_given
    a.passport_no = new_pp
    if body.is_minor is not None:
        a.is_minor = body.is_minor
    if body.guardian_relationship is not None:
        a.guardian_relationship = body.guardian_relationship or None
    if a.is_minor and not a.guardian_relationship:
        raise BizException(
            ErrorCode.INVALID_PARAMS,
            message="guardian_relationship is required for minor applicants",
        )
    await db.commit()
    await db.refresh(a)
    _log.info(
        "profile.applicant.update",
        extra={
            "user_id": current_user.id,
            "event_type": "profile.applicant.update",
            "applicant_id": a.id,
            "status": "success",
        },
    )
    return ApiResponse[ApplicantCreateResponse](
        code="1000",
        message="OK",
        data=ApplicantCreateResponse(applicant=_applicant_to_item(a)),
    )


# --------------------------------------------------------------------------- #
# DELETE /profile/applicants/{id}                                             #
# --------------------------------------------------------------------------- #
@router.delete(
    "/applicants/{applicant_id}",
    response_model=ApiResponse[dict],
    summary="Remove an applicant",
)
async def delete_applicant(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    applicant_id: int = Path(..., ge=1),
) -> ApiResponse[dict]:
    a = await _get_owned_applicant(db, applicant_id, current_user.id)
    await db.delete(a)
    await db.commit()
    _log.info(
        "profile.applicant.delete",
        extra={
            "user_id": current_user.id,
            "event_type": "profile.applicant.delete",
            "applicant_id": applicant_id,
            "status": "success",
        },
    )
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={"deleted": applicant_id},
    )


# --------------------------------------------------------------------------- #
# Email change flow                                                           #
# --------------------------------------------------------------------------- #
_EMAIL_CHANGE_TOKEN_TYPE = "email_change"
_EMAIL_CHANGE_TTL_MINUTES = 30


def _make_email_change_token(user_id: int, new_email: str) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=_EMAIL_CHANGE_TTL_MINUTES)
    payload = {
        "sub": str(user_id),
        "new_email": new_email,
        "type": _EMAIL_CHANGE_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, exp


def _decode_email_change_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise BizException(
            ErrorCode.EMAIL_CHANGE_TOKEN_INVALID, message="Invalid token"
        ) from None

    if payload.get("type") != _EMAIL_CHANGE_TOKEN_TYPE:
        raise BizException(
            ErrorCode.EMAIL_CHANGE_TOKEN_INVALID, message="Wrong token type"
        )
    exp = payload.get("exp")
    if exp is not None and datetime.fromtimestamp(int(exp), tz=timezone.utc) < datetime.now(timezone.utc):
        raise BizException(
            ErrorCode.EMAIL_CHANGE_TOKEN_EXPIRED, message="Token expired"
        )
    return payload


def _frontend_base() -> str:
    """Best-effort frontend base for the verification link.

    W1: in dev this is http://localhost:5173/profile/email/verify?token=...
    PROD: override via APP_FRONTEND_BASE env var.
    """
    return get_settings().app_frontend_base or "http://localhost:5173"


@router.post(
    "/email/change-request",
    response_model=ApiResponse[EmailChangeResponse],
    summary="Start an email change — re-auth + send verification link to the new email",
)
async def request_email_change(
    body: EmailChangeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[EmailChangeResponse]:
    new_email = body.new_email.lower().strip()

    if new_email == (current_user.email or "").lower().strip():
        raise BizException(
            ErrorCode.EMAIL_CHANGE_SAME_AS_CURRENT,
            message="The new email is the same as the current one",
        )

    # Re-auth via password (OAuth-only users set a password first or use a
    # separate "verify via current email" path — W1 is password-only).
    if not current_user.password_hash or not verify_password(body.password, current_user.password_hash):
        raise BizException(
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            message="Password is incorrect",
        )

    # Refuse if another account already owns this email.
    other = await db.execute(select(User).where(User.email == new_email))
    if other.scalars().first() is not None:
        raise BizException(
            ErrorCode.USER_ALREADY_EXISTS,
            message="This email is already registered to another account",
        )

    if current_user.email_pending and current_user.email_pending.lower() == new_email:
        raise BizException(
            ErrorCode.EMAIL_CHANGE_ALREADY_PENDING,
            message="A change to this email is already pending verification",
        )

    token, _exp = _make_email_change_token(current_user.id, new_email)
    confirm_url = f"{_frontend_base()}/profile/email/verify?token={token}"

    # Stash the pending email on the user row so we can finish on confirm.
    current_user.email_pending = new_email
    db.add(current_user)
    await db.commit()

    # Best-effort email send — never blocks the request.
    send_email_change_verification(
        EmailChangeVerification(
            to_email=new_email,
            nickname=current_user.nickname or current_user.username or "there",
            language_pref=current_user.language_pref or "en",
            confirm_url=confirm_url,
        ),
        new_email=new_email,
    )

    _log.info(
        "profile.email.change.request",
        extra={
            "user_id": current_user.id,
            "event_type": "profile.email.change.request",
            "new_email_hash": _email_hash(new_email),
            "status": "success",
        },
    )
    return ApiResponse[EmailChangeResponse](
        code="1000",
        message="OK",
        data=EmailChangeResponse(
            message="Verification link sent to the new email address",
            pending_email=new_email,
        ),
    )


@router.post(
    "/email/change-confirm",
    response_model=ApiResponse[EmailChangeResponse],
    summary="Confirm an email change with the token from the verification email",
)
async def confirm_email_change(
    body: EmailChangeConfirm,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[EmailChangeResponse]:
    payload = _decode_email_change_token(body.token)
    try:
        sub_user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise BizException(
            ErrorCode.EMAIL_CHANGE_TOKEN_INVALID, message="Bad token subject"
        ) from None
    if sub_user_id != current_user.id:
        raise BizException(
            ErrorCode.EMAIL_CHANGE_TOKEN_INVALID, message="Token does not belong to this user"
        )

    new_email = (payload.get("new_email") or "").lower().strip()
    if not new_email or new_email == (current_user.email or "").lower().strip():
        raise BizException(
            ErrorCode.EMAIL_CHANGE_SAME_AS_CURRENT,
            message="Token does not match a pending change",
        )

    # Re-check uniqueness in case someone else registered the email in the meantime.
    other = await db.execute(
        select(User).where(User.email == new_email, User.id != current_user.id)
    )
    if other.scalars().first() is not None:
        raise BizException(
            ErrorCode.USER_ALREADY_EXISTS,
            message="This email is already registered to another account",
        )

    current_user.email = new_email
    current_user.email_pending = None
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    _log.info(
        "profile.email.change.confirm",
        extra={
            "user_id": current_user.id,
            "event_type": "profile.email.change.confirm",
            "status": "success",
        },
    )
    return ApiResponse[EmailChangeResponse](
        code="1000",
        message="OK",
        data=EmailChangeResponse(message="Email updated", pending_email=None),
    )


@router.post(
    "/email/change-cancel",
    response_model=ApiResponse[EmailChangeResponse],
    summary="Cancel a pending email change",
)
async def cancel_email_change(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[EmailChangeResponse]:
    if current_user.email_pending:
        current_user.email_pending = None
        db.add(current_user)
        await db.commit()
    return ApiResponse[EmailChangeResponse](
        code="1000",
        message="OK",
        data=EmailChangeResponse(message="Pending change cancelled", pending_email=None),
    )


@router.post(
    "/delete-account",
    response_model=ApiResponse[dict],
    summary="Request account deletion (72h grace period, then permanent purge)",
)
async def delete_account(
    body: AccountDeleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    if not body.confirm:
        raise BizException(ErrorCode.INVALID_PARAMS, message="Deletion must be explicitly confirmed")

    if current_user.status == "pending_destroy":
        return ApiResponse[dict](
            code="1000",
            message="OK",
            data={"message": "Account deletion already scheduled", "status": "pending_destroy"},
        )

    has_password = bool(current_user.password_hash)
    if has_password:
        if not body.password or not verify_password(body.password, current_user.password_hash):
            raise BizException(
                ErrorCode.AUTH_INVALID_CREDENTIALS,
                message="Password is incorrect",
            )
    # OAuth-only: confirm flag is sufficient (no password to verify).

    current_user.status = "pending_destroy"
    db.add(current_user)
    await db.commit()

    _log.info(
        "profile.account.delete.requested",
        extra={
            "user_id": current_user.id,
            "event_type": "profile.account.delete.requested",
            "status": "pending_destroy",
        },
    )
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={
            "message": "Account scheduled for deletion. Data will be permanently removed after 72 hours. You may cancel within that window.",
            "status": "pending_destroy",
            "support_email": get_settings().privacy_support_email,
        },
    )


@router.post(
    "/cancel-delete-account",
    response_model=ApiResponse[dict],
    summary="Cancel a pending account deletion within the 72h grace period",
)
async def cancel_delete_account(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    if current_user.status == "active":
        return ApiResponse[dict](
            code="1000",
            message="OK",
            data={"message": "Account is active", "status": "active"},
        )
    if current_user.status != "pending_destroy":
        raise BizException(
            ErrorCode.ACCOUNT_DISABLED,
            message="Account cannot cancel deletion in current status",
        )
    current_user.status = "active"
    db.add(current_user)
    await db.commit()
    _log.info(
        "profile.account.delete.cancelled",
        extra={
            "user_id": current_user.id,
            "event_type": "profile.account.delete.cancelled",
            "status": "active",
        },
    )
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={"message": "Account deletion cancelled", "status": "active"},
    )


@router.get(
    "/consents",
    response_model=ApiResponse[dict],
    summary="List consent records for the current user",
)
async def list_consents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    from app.services.consent_service import ConsentService

    items = await ConsentService(db).list_for_user(current_user.id)
    return ApiResponse[dict](code="1000", message="OK", data={"items": items})


@router.post(
    "/consents",
    response_model=ApiResponse[dict],
    summary="Grant purpose-bound consent",
)
async def grant_consent(
    body: ConsentGrantRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    from app.services.consent_service import ConsentService

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    row = await ConsentService(db).grant(
        current_user, body.purpose, version=body.version, ip=ip, user_agent=ua
    )
    await db.commit()
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={
            "purpose": row.purpose,
            "version": row.version,
            "granted_at": row.granted_at.isoformat() if row.granted_at else None,
            "active": True,
        },
    )


@router.post(
    "/consents/revoke",
    response_model=ApiResponse[dict],
    summary="Revoke a previously granted consent",
)
async def revoke_consent(
    body: ConsentRevokeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    from app.services.consent_service import ConsentService

    ok = await ConsentService(db).revoke(current_user, body.purpose, version=body.version)
    await db.commit()
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={"purpose": body.purpose, "revoked": ok},
    )


@router.post(
    "/processing-restriction",
    response_model=ApiResponse[dict],
    summary="Set Art.18 restriction / Art.21 objection flag",
)
async def set_processing_restriction(
    body: ProcessingRestrictionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    current_user.processing_restricted = bool(body.restricted)
    db.add(current_user)
    await db.commit()
    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={"processing_restricted": current_user.processing_restricted},
    )


@router.get(
    "/data-export",
    response_model=ApiResponse[dict],
    summary="Export account data (Art.15 / Art.20 portable JSON)",
)
async def export_my_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict]:
    import json
    from app.models.order import Order
    from app.services.consent_service import ConsentService

    applicants = (
        await db.execute(select(Applicant).where(Applicant.user_id == current_user.id))
    ).scalars().all()
    orders = (
        await db.execute(select(Order).where(Order.user_id == current_user.id))
    ).scalars().all()
    consents = await ConsentService(db).list_for_user(current_user.id)

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": current_user.id,
            "uuid": current_user.uuid,
            "email": current_user.email,
            "username": current_user.username,
            "nickname": current_user.nickname,
            "language_pref": current_user.language_pref,
            "status": current_user.status,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "processing_restricted": bool(current_user.processing_restricted),
        },
        "applicants": [
            {
                "id": a.id,
                "surname": a.surname,
                "given_name": a.given_name,
                "passport_no": a.passport_no,
                "is_minor": bool(a.is_minor),
                "guardian_relationship": a.guardian_relationship,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in applicants
        ],
        "orders": [
            {
                "order_no": o.order_no,
                "status": o.status,
                "destination_id": getattr(o, "destination_id", None),
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "paid_at": o.paid_at.isoformat() if getattr(o, "paid_at", None) else None,
                # Include applicant snapshot only as structured JSON if present
                "applicant_data": json.loads(o.applicant_data) if o.applicant_data else None,
            }
            for o in orders
        ],
        "consents": consents,
    }
    return ApiResponse[dict](code="1000", message="OK", data=payload)


# --------------------------------------------------------------------------- #
# Tiny helpers                                                                #
# --------------------------------------------------------------------------- #
_EMAIL_HASH_RE = re.compile(r"^(.).+(@.+)$")


def _email_hash(email: str) -> str:
    """Cheaply anonymize an email for logs (preserves domain for debugging).

    Example: 'alice@example.com' -> 'a***@example.com'
    """
    try:
        local, domain = email.split("@", 1)
        if not local:
            return f"***@{domain}"
        return f"{local[0]}***@{domain}"
    except Exception:
        return "***"
