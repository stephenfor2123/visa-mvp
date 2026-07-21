"""Local-filesystem storage adapter for materials.

Stand-in for MinIO in W2 — same surface area (write/read/signed URL) so
that swapping in a real S3/MinIO client later is a one-file change.

Layout on disk:
    {STORAGE_ROOT}/{user_id}/{YYYY}/{MM}/{uuid}{ext}

When MATERIAL_ENCRYPTION_KEY is set, payloads are AES-GCM encrypted at rest
(prefix magic `HTX1` + 12-byte nonce + ciphertext+tag).
"""
import base64
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
_ENC_MAGIC = b"HTX1"


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


def _resolve_aes_key() -> Optional[bytes]:
    """Return 32-byte AES key or None (plaintext mode for local/dev)."""
    raw = (get_settings().material_encryption_key or "").strip()
    if not raw:
        if get_settings().env == "prod":
            raise RuntimeError(
                "MATERIAL_ENCRYPTION_KEY must be set in production "
                "(32-byte urlsafe base64 or 64 hex chars)"
            )
        return None
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return bytes.fromhex(raw)
    pad = "=" * (-len(raw) % 4)
    try:
        key = base64.urlsafe_b64decode(raw + pad)
    except Exception:
        key = base64.b64decode(raw + pad)
    if len(key) != 32:
        raise ValueError("MATERIAL_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def encryption_key_id() -> str:
    key = _resolve_aes_key()
    if key is None:
        return "none"
    return get_settings().material_encryption_key_id or "local-aes-gcm-v1"


def _encrypt_bytes(data: bytes) -> bytes:
    key = _resolve_aes_key()
    if key is None:
        return data
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(nonce, data, None)
    return _ENC_MAGIC + nonce + ct


def _decrypt_bytes(data: bytes) -> bytes:
    if not data.startswith(_ENC_MAGIC):
        return data
    key = _resolve_aes_key()
    if key is None:
        raise RuntimeError("Encrypted material requires MATERIAL_ENCRYPTION_KEY")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = data[4:16]
    ct = data[16:]
    return AESGCM(key).decrypt(nonce, ct, None)


def _signing_secret() -> str:
    return get_settings().jwt_secret


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


@dataclass
class StoredFile:
    storage_key: str
    abs_path: Path
    size: int
    encryption_key_id: str = "none"


def store_bytes(
    user_id: int, ext: str, data: bytes, *, prefix: str = ""
) -> StoredFile:
    """Write `data` under `{root}/{user_id}/YYYY/MM/{prefix}{uuid}{ext}`."""
    import uuid
    from datetime import datetime

    now = datetime.utcnow()
    suffix = f".{ext.lstrip('.').lower()}" if ext else ""
    rand = uuid.uuid4().hex
    fname = f"{prefix}{rand}{suffix}"
    rel = Path(str(user_id)) / f"{now.year:04d}" / f"{now.month:02d}" / fname
    abs_path = get_storage_root() / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _encrypt_bytes(data)
    abs_path.write_bytes(payload)
    return StoredFile(
        storage_key=str(rel).replace(os.sep, "/"),
        abs_path=abs_path,
        size=len(data),
        encryption_key_id=encryption_key_id(),
    )


def read_bytes(storage_key: str) -> bytes:
    """Read a stored file by its key. Caller is responsible for auth/URL checks."""
    root = get_storage_root()
    abs_path = (root / storage_key).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError as exc:
        raise FileNotFoundError(storage_key) from exc
    return _decrypt_bytes(abs_path.read_bytes())


def path_for(storage_key: str) -> Path:
    root = get_storage_root()
    abs_path = (root / storage_key).resolve()
    try:
        abs_path.relative_to(root)
    except ValueError as exc:
        raise FileNotFoundError(storage_key) from exc
    return abs_path


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def random_token(nbytes: int = 16) -> str:
    return secrets.token_hex(nbytes)
