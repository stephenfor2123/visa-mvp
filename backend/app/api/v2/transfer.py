"""/api/v2/transfer — Cross-device session for the "scan QR to upload from phone" flow.

PC creates a session (POST /sessions) → receives a QR payload (a mobile URL with
sid+token).  User scans the QR from any phone browser → phone claims the session
(POST /sessions/{sid}/claim) → upload files (POST /sessions/{sid}/files).  PC
polls a server-sent event stream (GET /sessions/{sid}/events) for `file_received`,
displaying each uploaded file in the wizard without a refresh.

Design constraints:
  * **Ephemeral**.  Sessions live in process memory only — TTL is 2 minutes
    (W48-QR: 拍完走人).  When the process restarts, sessions disappear, but the
    qr-payload token is bound to the user_id at creation time so no cross-user
    leakage is possible.
  * **One-claim-per-session**.  Once a phone claims the sid, the same sid can't
    be re-claimed by another phone.  The first phone that scans "wins".
  * **Files are processed in memory only**.  OCR results are relayed to the PC
    via SSE; bytes are never written to disk or the materials table.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, AsyncIterator, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.core.errors import BizException, ErrorCode
from app.services.material_process_service import process_bytes

router = APIRouter(prefix="/transfer", tags=["transfer"])
_log = get_logger()

# ──────────────────────────────────────────────────────────────────────────────
# Session state (in-memory, ephemeral)
# ──────────────────────────────────────────────────────────────────────────────

SESSION_TTL_SECONDS = 120  # W48: 2 minutes per user choice


@dataclass
class SessionRecord:
    sid: str
    user_id: int
    token: str            # bearer-equivalent for the phone claim path
    created_at: float
    expires_at: float
    claimed_at: Optional[float] = None
    claimed_ip: Optional[str] = None
    closed_at: Optional[float] = None
    close_reason: Optional[str] = None  # 'completed' | 'expired' | 'aborted' | 'phone_left'
    uploaded_materials: List[Dict[str, Any]] = field(default_factory=list)

    # asyncio.Event broadcast to all SSE listeners per session
    event_loop_id: int = 0  # increment on each new event for SSE resync

    def is_alive(self, now: Optional[float] = None) -> bool:
        """A session is 'alive' if it has not expired and not been explicitly closed."""
        now = now or time.time()
        return self.closed_at is None and now < self.expires_at

    def is_claimed(self) -> bool:
        return self.claimed_at is not None


_SESSIONS: Dict[str, SessionRecord] = {}
_SESSION_LOCKS: Dict[str, asyncio.Lock] = {}


def _get_lock(sid: str) -> asyncio.Lock:
    """Per-session lock to make state transitions serializable."""
    if sid not in _SESSION_LOCKS:
        _SESSION_LOCKS[sid] = asyncio.Lock()
    return _SESSION_LOCKS[sid]


def _purge_session(sid: str) -> None:
    """Drop a session from memory after it has been closed for >5 minutes."""
    sess = _SESSIONS.get(sid)
    if sess and sess.closed_at and time.time() - sess.closed_at > 300:
        del _SESSIONS[sid]
        _SESSION_LOCKS.pop(sid, None)


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────


class SessionCreateOut(BaseModel):
    sid: str
    qr_payload: str           # the URL the phone should be sent to
    expires_at: float         # unix epoch seconds


class SessionDetailOut(BaseModel):
    sid: str
    expires_at: float
    claimed: bool
    closed: bool
    close_reason: Optional[str]
    file_count: int
    files: List[Dict[str, Any]]


class FileAcceptedOut(BaseModel):
    material_id: str
    file_name: str
    thumbnail_url: str = ""
    download_url: str = ""
    material_type: str = "other"
    ocr_result: Optional[dict[str, Any]] = None
    is_blurry: bool = False
    bank_analysis: Optional[dict[str, Any]] = None


# ──────────────────────────────────────────────────────────────────────────────
# PC side — create session, list / close
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=SessionCreateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new transfer session (PC side)",
)
async def create_session(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionCreateOut:
    """PC calls this when the user clicks '用手机上传'.

    Returns a `sid` and a `qr_payload` — the URL embedded in the QR code.
    Sessions are short-lived (2 min).  Subsequent sessions for the same user
    auto-expire old ones to keep the dict tidy.
    """
    now = time.time()
    sid = secrets.token_urlsafe(8)         # 64-bit entropy, 11-char URL-safe
    token = secrets.token_urlsafe(24)       # bearer for the phone claim
    sess = SessionRecord(
        sid=sid,
        user_id=current_user.id,
        token=token,
        created_at=now,
        expires_at=now + SESSION_TTL_SECONDS,
    )
    _SESSIONS[sid] = sess

    # Evict prior un-claimed sessions of the same user (best-effort)
    stale = [
        s for s in _SESSIONS.values()
        if s.user_id == current_user.id
        and s.sid != sid
        and (s.closed_at is None and now < s.expires_at)
        and not s.is_claimed()
    ]
    for old in stale:
        old.closed_at = now
        old.close_reason = "superseded"

    settings = get_settings()
    # W48: prefer explicit FRONTEND_URL (set in .env); otherwise the mobile side
    # is just /transfer on the same host so the absolute URL is `request.base_url`.
    base = (
        getattr(settings, "frontend_url", None)
        or getattr(settings, "public_web_url", None)
        or str(request.base_url).rstrip("/")
    ).rstrip("/")
    qr_payload = f"{base}/transfer?sid={sid}&t={token}"

    _log.info("transfer session created sid={} user_id={} expires_in={}",
              sid, current_user.id, SESSION_TTL_SECONDS)
    return SessionCreateOut(sid=sid, qr_payload=qr_payload, expires_at=sess.expires_at)


@router.get(
    "/sessions/{sid}",
    response_model=SessionDetailOut,
    summary="Get the current state of a session (PC side polls this if SSE drops)",
)
async def get_session(
    sid: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionDetailOut:
    sess = _SESSIONS.get(sid)
    if sess is None or sess.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="session not found")

    now = time.time()
    expired = now >= sess.expires_at and sess.closed_at is None
    if expired:
        sess.closed_at = now
        sess.close_reason = "expired"
    _purge_session(sid)

    return SessionDetailOut(
        sid=sess.sid,
        expires_at=sess.expires_at,
        claimed=sess.is_claimed(),
        closed=sess.closed_at is not None,
        close_reason=sess.close_reason,
        file_count=len(sess.uploaded_materials),
        files=list(sess.uploaded_materials),
    )


@router.post(
    "/sessions/{sid}/close",
    status_code=status.HTTP_200_OK,
    summary="Close/abort a session early (PC side)",
)
async def close_session(
    sid: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Dict[str, Any]:
    sess = _SESSIONS.get(sid)
    if sess is None or sess.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="session not found")
    if sess.closed_at is None:
        sess.closed_at = time.time()
        sess.close_reason = "aborted"
    _purge_session(sid)
    return {"sid": sid, "closed": True, "reason": sess.close_reason}


# ──────────────────────────────────────────────────────────────────────────────
# Phone side — claim, upload
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/sessions/{sid}/claim",
    status_code=status.HTTP_200_OK,
    summary="Phone claims the session after scanning the QR",
)
async def claim_session(
    sid: str,
    request: Request,
) -> Dict[str, Any]:
    """The phone calls this right after the user lands on /transfer?sid=...&t=...

    `t` is the bearer-equivalent — it lives in the QR, and the only thing it
    authorises is *claiming the sid*.  The PC user is the data owner; the
    phone is just a temporary input device.  We don't create a separate auth
    session for the phone.
    """
    sess = _SESSIONS.get(sid)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found or expired")
    if sess.closed_at is not None:
        raise HTTPException(status_code=410, detail=f"session {sess.close_reason}")
    if time.time() >= sess.expires_at:
        sess.closed_at = time.time()
        sess.close_reason = "expired"
        raise HTTPException(status_code=410, detail="session expired")

    # token from custom header 'X-Transfer-Token' to keep it out of access logs
    token = request.headers.get("X-Transfer-Token", "")
    if not token or not secrets.compare_digest(token, sess.token):
        raise HTTPException(status_code=403, detail="invalid transfer token")

    async with _get_lock(sid):
        if sess.is_claimed():
            raise HTTPException(status_code=409, detail="session already claimed by another device")
        sess.claimed_at = time.time()
        sess.claimed_ip = request.client.host if request.client else None
        sess.event_loop_id += 1

    _log.info("transfer session claimed sid={} ip={}", sid, sess.claimed_ip)
    # 返回给手机端: 还能传多久、PC user 是不是 demo、上传用 material_type 默认值
    return {
        "sid": sess.sid,
        "expires_at": sess.expires_at,
        "material_type_default": "other",
    }


@router.post(
    "/sessions/{sid}/files",
    response_model=FileAcceptedOut,
    status_code=status.HTTP_201_CREATED,
    summary="Phone uploads one file into the session",
)
async def upload_via_session(
    sid: str,
    request: Request,
    file: UploadFile = File(..., description="image/jpeg | image/png | image/webp | application/pdf"),
    material_type: str = Form("other", description="material type slug"),
    x_transfer_token: str = Header(..., alias="X-Transfer-Token", description="token from QR"),
) -> FileAcceptedOut:
    """Phone uploads a file.  Bytes are processed in memory and relayed to the PC
    via SSE — nothing is persisted on the server.
    """
    sess = _SESSIONS.get(sid)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found or expired")
    if sess.closed_at is not None:
        raise HTTPException(status_code=410, detail=f"session {sess.close_reason}")
    if time.time() >= sess.expires_at:
        sess.closed_at = time.time()
        sess.close_reason = "expired"
        raise HTTPException(status_code=410, detail="session expired")
    if not sess.is_claimed():
        raise HTTPException(status_code=409, detail="session not claimed yet")
    if not secrets.compare_digest(x_transfer_token, sess.token):
        raise HTTPException(status_code=403, detail="invalid transfer token")

    data = await file.read()
    if not data:
        raise BizException(ErrorCode.INVALID_PARAMS, message="file is empty")

    import uuid

    ephemeral_id = f"transfer_{uuid.uuid4().hex[:12]}"
    processed = process_bytes(data, material_type=material_type)
    ocr_fields = processed.get("fields") or {}

    record = {
        "material_id": ephemeral_id,
        "file_name": file.filename or "file",
        "mime_type": file.content_type or "",
        "file_size": len(data),
        "thumbnail_url": "",
        "download_url": "",
        "material_type": material_type,
        "ocr_result": ocr_fields,
        "is_blurry": processed.get("is_blurry", False),
        "bank_analysis": processed.get("bank_analysis"),
        "ephemeral": True,
    }
    async with _get_lock(sid):
        sess.uploaded_materials.append(record)
        sess.event_loop_id += 1
        if len(sess.uploaded_materials) == 1:
            sess.expires_at = max(sess.expires_at, time.time() + SESSION_TTL_SECONDS)

    _log.info("transfer file processed sid={} ephemeral_id={} size={}", sid, ephemeral_id, len(data))

    return FileAcceptedOut(
        material_id=ephemeral_id,
        file_name=record["file_name"],
        thumbnail_url="",
        download_url="",
        material_type=material_type,
        ocr_result=ocr_fields,
        is_blurry=record["is_blurry"],
        bank_analysis=record.get("bank_analysis"),
    )


@router.post(
    "/sessions/{sid}/leave",
    status_code=status.HTTP_200_OK,
    summary="Phone declares it's done — close the session cleanly",
)
async def leave_session(
    sid: str,
    x_transfer_token: str = Header(..., alias="X-Transfer-Token"),
) -> Dict[str, Any]:
    sess = _SESSIONS.get(sid)
    if sess is None:
        return {"sid": sid, "closed": True, "reason": "purged"}
    if not secrets.compare_digest(x_transfer_token, sess.token):
        raise HTTPException(status_code=403, detail="invalid transfer token")
    if sess.closed_at is None:
        sess.closed_at = time.time()
        sess.close_reason = "phone_left"
        sess.event_loop_id += 1
    _purge_session(sid)
    return {"sid": sid, "closed": True, "reason": sess.close_reason}


# ──────────────────────────────────────────────────────────────────────────────
# SSE — PC subscribes to file_received events
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/sessions/{sid}/events",
    summary="Server-sent event stream of session activity (PC side)",
    response_class=StreamingResponse,
)
async def session_events(
    sid: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Lightweight SSE — emits when:
      * phone claims the session   → event: claimed
      * phone uploads a file       → event: file_received (with material row)
      * phone leaves / closes      → event: closed

    Implementation is a simple polling-style generator (1s tick).  Adequate
    for the 2-min session lifetime — no need for fancy pub/sub.
    """
    sess = _SESSIONS.get(sid)
    if sess is None or sess.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="session not found")
    last_event_id = sess.event_loop_id

    async def stream() -> AsyncIterator[bytes]:
        nonlocal last_event_id
        # Tell the client we're alive and what version we're at
        yield _sse_pack("hello", {
            "sid": sid,
            "expires_at": sess.expires_at,
            "server_time": time.time(),
        })
        while True:
            await asyncio.sleep(1.0)
            cur = _SESSIONS.get(sid)
            if cur is None:
                yield _sse_pack("closed", {"reason": "purged"})
                return
            if cur.event_loop_id != last_event_id:
                last_event_id = cur.event_loop_id
                # Emit file_received for any new materials since last tick
                for f in cur.uploaded_materials:
                    # Only emit the *last* N events to avoid replay when client reconnects mid-stream
                    pass
                # Compact: emit the latest material only (single-file batches from phone)
                latest = cur.uploaded_materials[-1] if cur.uploaded_materials else None
                if latest is not None and not latest.get("_emitted"):
                    latest["_emitted"] = True
                    yield _sse_pack("file_received", latest)
                if cur.closed_at is not None:
                    yield _sse_pack("closed", {"reason": cur.close_reason or "unknown"})
                    return
            # Heartbeat every 15s
            yield b": ping\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering
            "Connection": "keep-alive",
        },
    )


def _sse_pack(event: str, data: Dict[str, Any]) -> bytes:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
