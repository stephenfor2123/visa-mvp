"""/api/v2/voice — speech-to-text + structured field extraction endpoint (V2 §3.3.3).

W14-5: accept a short audio clip, run ASR, and return a structured applicant
dict ready for the front-end Materials auto-fill flow.
"""
import time
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import BizException, ErrorCode
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.audit import record_audit
from app.services.voice_input import (
    MAX_AUDIO_BYTES,
    MIN_AUDIO_BYTES,
    SUPPORTED_LANGS,
    VoiceInputError,
    recognize_speech,
)

router = APIRouter(tags=["voice"])
_log = get_logger()


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #
class VoiceRecognizeOut(Dict[str, Any]):
    """Response payload — the same shape returned by
    :func:`app.services.voice_input.recognize_speech`.  We expose it via
    ``ApiResponse[dict]`` so the envelope stays uniform across the v2 API.
    """


# --------------------------------------------------------------------------- #
# Endpoint                                                                    #
# --------------------------------------------------------------------------- #
@router.post(
    "/recognize",
    response_model=ApiResponse[dict],
    summary="Voice recognize — speech-to-text + structured fields (V2 §3.3.3)",
)
async def recognize(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(..., description="Audio file (WAV/MP3/OGG/FLAC/MP4/WebM)"),
    lang: str = Form(default="en", description="Recognition language: zh-CN / en / id / vi"),
) -> ApiResponse[dict]:
    """
    POST /api/v2/voice/recognize

    - JWT auth required (Authorization: Bearer ...)
    - multipart upload: ``file`` + ``lang``
    - Returns: ``{name, address, travel_date, raw_text, lang, confidence, engine, ...}``

    Errors
    ------
    * ``2003 VOICE_AUDIO_FORMAT`` — bad / missing / oversized audio (HTTP 400)
    * ``2004 VOICE_RECOGNIZE_FAILED`` — engine could not transcribe (HTTP 422)
    * ``2005 VOICE_TIMEOUT`` — engine exceeded the timeout (HTTP 504)
    """
    started = time.monotonic()
    log_ctx = {"user_id": current_user.id, "lang": lang}

    # W19-2: helper to audit pre-flight errors (before recognize_speech runs)
    async def _audit_preflight_error(error_code: str, error_message: str) -> None:
        try:
            await record_audit(
                db,
                actor_type="user",
                actor_id=current_user.id,
                action="voice.recognize",
                target_type="voice",
                target_id=None,
                payload={
                    "lang": lang,
                    "audio_size": 0,
                    "result": "error",
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )
            await db.commit()
        except Exception as audit_exc:
            _log.warning("audit write failed for voice: {}", audit_exc)

    if not file or not file.filename:
        _log.warning("voice recognize: missing file | {}", log_ctx)
        await _audit_preflight_error("VOICE_AUDIO_FORMAT", "Audio file is required")
        raise BizException(
            ErrorCode.VOICE_AUDIO_FORMAT,
            message="Audio file is required",
        )

    if lang not in SUPPORTED_LANGS:
        _log.warning("voice recognize: bad lang={} | {}", lang, log_ctx)
        await _audit_preflight_error(
            "VOICE_AUDIO_FORMAT",
            f"Unsupported language: {lang!r}. Supported: {', '.join(SUPPORTED_LANGS)}",
        )
        raise BizException(
            ErrorCode.VOICE_AUDIO_FORMAT,
            message=f"Unsupported language: {lang!r}. "
                    f"Supported: {', '.join(SUPPORTED_LANGS)}",
        )

    try:
        content = await file.read()
    except Exception as exc:  # noqa: BLE001
        _log.error("voice recognize: read failed: {} | {}", exc, log_ctx)
        await _audit_preflight_error("VOICE_AUDIO_FORMAT", f"Failed to read upload: {exc}")
        raise BizException(
            ErrorCode.VOICE_AUDIO_FORMAT,
            message=f"Failed to read upload: {exc}",
        )

    if not content or len(content) < MIN_AUDIO_BYTES:
        _log.warning(
            "voice recognize: too small ({} bytes) | {}",
            len(content) if content else 0,
            log_ctx,
        )
        await _audit_preflight_error(
            "VOICE_AUDIO_FORMAT",
            f"Audio payload too small (<{MIN_AUDIO_BYTES} bytes)",
        )
        raise BizException(
            ErrorCode.VOICE_AUDIO_FORMAT,
            message=f"Audio payload too small (<{MIN_AUDIO_BYTES} bytes)",
        )
    if len(content) > MAX_AUDIO_BYTES:
        _log.warning(
            "voice recognize: too large ({} bytes) | {}",
            len(content),
            log_ctx,
        )
        await _audit_preflight_error(
            "VOICE_AUDIO_FORMAT",
            f"Audio payload too large (>{MAX_AUDIO_BYTES} bytes)",
        )
        raise BizException(
            ErrorCode.VOICE_AUDIO_FORMAT,
            message=f"Audio payload too large (>{MAX_AUDIO_BYTES} bytes)",
        )

    try:
        fields = recognize_speech(content, lang)
    except VoiceInputError as exc:
        _log.warning(
            "voice recognize: structured error code={} msg={} elapsed={}ms | {}",
            exc.code,
            exc.message,
            int((time.monotonic() - started) * 1000),
            log_ctx,
        )
        # W19-2: 合规审计 — 失败也留痕
        try:
            await record_audit(
                db,
                actor_type="user",
                actor_id=current_user.id,
                action="voice.recognize",
                target_type="voice",
                target_id=None,
                payload={
                    "lang": lang,
                    "audio_size": len(content) if content else 0,
                    "result": "error",
                    "error_code": exc.code,
                    "error_message": exc.message,
                },
            )
            await db.commit()
        except Exception as audit_exc:
            _log.warning("audit write failed for voice: {}", audit_exc)
        if exc.code == "VOICE_TIMEOUT":
            raise BizException(ErrorCode.VOICE_TIMEOUT, message=exc.message) from None
        if exc.code == "VOICE_RECOGNIZE_FAILED":
            raise BizException(ErrorCode.VOICE_RECOGNIZE_FAILED, message=exc.message) from None
        raise BizException(ErrorCode.VOICE_AUDIO_FORMAT, message=exc.message) from None
    except Exception as exc:  # noqa: BLE001
        _log.error("voice recognize: unexpected: {} | {}", exc, log_ctx)
        try:
            await record_audit(
                db,
                actor_type="user",
                actor_id=current_user.id,
                action="voice.recognize",
                target_type="voice",
                target_id=None,
                payload={
                    "lang": lang,
                    "audio_size": len(content) if content else 0,
                    "result": "error",
                    "error_code": "UNEXPECTED",
                    "error_message": str(exc),
                },
            )
            await db.commit()
        except Exception as audit_exc:
            _log.warning("audit write failed for voice: {}", audit_exc)
        raise BizException(
            ErrorCode.VOICE_RECOGNIZE_FAILED,
            message="Unexpected error during recognition",
        ) from None

    elapsed_ms = int((time.monotonic() - started) * 1000)
    _log.info(
        "voice recognize: ok user={} lang={} engine={} "
        "name={} address={} travel_date={} elapsed={}ms",
        current_user.id,
        lang,
        fields.get("engine"),
        fields.get("name"),
        bool(fields.get("address")),
        fields.get("travel_date"),
        elapsed_ms,
    )
    # W19-2: 合规审计 — 成功路径
    try:
        await record_audit(
            db,
            actor_type="user",
            actor_id=current_user.id,
            action="voice.recognize",
            target_type="voice",
            target_id=None,
            payload={
                "lang": lang,
                "audio_size": len(content) if content else 0,
                "result": "ok",
                "engine": fields.get("engine"),
                "elapsed_ms": elapsed_ms,
                # 只标记哪些字段被抽到了, 不存 PII 原文
                "extracted_fields": {
                    k: (bool(v) and len(str(v)) if v else False)
                    for k, v in fields.items()
                    if k != "raw_text"
                },
            },
        )
        await db.commit()
    except Exception as audit_exc:
        _log.warning("audit write failed for voice: {}", audit_exc)
    return ApiResponse[dict](code="1000", message="OK", data=fields)


# --------------------------------------------------------------------------- #
# Introspection helpers (handy for ops + tests)                              #
# --------------------------------------------------------------------------- #
@router.get(
    "/config",
    response_model=ApiResponse[dict],
    summary="Voice endpoint configuration",
)
async def get_config() -> ApiResponse[dict]:
    """Lightweight introspection endpoint — no auth required.

    Exposes the supported languages + audio limits so the front-end can
    validate inputs before round-tripping the upload.
    """
    import os

    return ApiResponse[dict](
        code="1000",
        message="OK",
        data={
            "supported_langs": list(SUPPORTED_LANGS),
            "min_audio_bytes": MIN_AUDIO_BYTES,
            "max_audio_bytes": MAX_AUDIO_BYTES,
            "active_engine": os.getenv("VOICE_ENGINE", "mock"),
        },
    )
