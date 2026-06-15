"""Local-filesystem storage adapter for materials.

Stand-in for MinIO in W2 — same surface area (write/read/signed URL) so
that swapping in a real S3/MinIO client later is a one-file change.

Layout on disk:
    {STORAGE_ROOT}/{user_id}/{YYYY}/{MM}/{uuid}{ext}

The signed URL is just an internal `/api/v2/materials/_local/{token}`
path where `token = sha256(storage_key + expires_at + secret)`. Tokens
expire after `url_ttl_seconds` (default 300s = 5min per V2 §4.3.1).
"""
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.config import get_settings


_STORAGE_ROOT: Optional[Path] = None


def get_storage_root() -> Path:
    """Resolve & cache the storage root. Created on first access."""
    global _STORAGE_ROOT
    if _STORAGE_ROOT is None:
        root = Path(get_settings().material_storage_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        _STORAGE_ROOT = root
    return _STORAGE_ROOT


def reset_storage_root_for_tests(root: Path) -> None:
    """Test helper: redirect storage to a temp dir."""
    global _STORAGE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    _STORAGE_ROOT = root


# --------------------------------------------------------------------------- #
# Signed URLs                                                                 #
# --------------------------------------------------------------------------- #
def _signing_secret() -> str:
    s = get_settings()
    # Reuse jwt_secret so we don't need yet another env var in dev.
    return s.jwt_secret


def make_signed_token(storage_key: str, ttl_seconds: int) -> tuple[str, int]:
    """Return (token, expires_at_unix)."""
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{storage_key}|{expires_at}"
    sig = hmac.new(
        _signing_secret().encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{expires_at}.{sig}", expires_at


def verify_signed_token(token: str, storage_key: str) -> bool:
    """Return True iff token is well-formed, not expired, and matches key."""
    try:
        expires_str, sig = token.split(".", 1)
        expires_at = int(expires_str)
    except (ValueError, AttributeError):
        return False
    if expires_at < int(time.time()):
        return False
    expected_sig = hmac.new(
        _signing_secret().encode("utf-8"),
        f"{storage_key}|{expires_at}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected_sig)


# --------------------------------------------------------------------------- #
# File I/O                                                                    #
# --------------------------------------------------------------------------- #
@dataclass
class StoredFile:
    storage_key: str
    abs_path: Path
    size: int


def store_bytes(
    user_id: int, ext: str, data: bytes, *, prefix: str = ""
) -> StoredFile:
    """Write `data` under `{root}/{user_id}/YYYY/MM/{prefix}{uuid}{ext}`.

    Returns the storage key (relative to root) and absolute path.
    """
    import uuid
    from datetime import datetime

    now = datetime.utcnow()
    suffix = f".{ext.lstrip('.').lower()}" if ext else ""
    rand = uuid.uuid4().hex
    fname = f"{prefix}{rand}{suffix}"
    rel = Path(str(user_id)) / f"{now.year:04d}" / f"{now.month:02d}" / fname
    abs_path = get_storage_root() / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)
    return StoredFile(
        storage_key=str(rel).replace(os.sep, "/"),
        abs_path=abs_path,
        size=len(data),
    )


def read_bytes(storage_key: str) -> bytes:
    """Read a stored file by its key. Caller is responsible for auth/URL checks."""
    # Defense in depth: resolve and confirm it's still under the root.
    root = get_storage_root()
    abs_path = (root / storage_key).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError as exc:  # attempted path traversal
        raise FileNotFoundError(storage_key) from exc
    return abs_path.read_bytes()


def path_for(storage_key: str) -> Path:
    root = get_storage_root()
    abs_path = (root / storage_key).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError as exc:
        raise FileNotFoundError(storage_key) from exc
    return abs_path


# --------------------------------------------------------------------------- #
# Utility                                                                     #
# --------------------------------------------------------------------------- #
def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def random_token(nbytes: int = 16) -> str:
    return secrets.token_hex(nbytes)
