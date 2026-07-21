"""Material at-rest encryption (AES-GCM) + signed-URL decryption on serve.

When MATERIAL_ENCRYPTION_KEY is set, files are AES-GCM encrypted on disk
(magic `HTX1` + nonce + ciphertext).  The signed-URL serve endpoint MUST
decrypt before returning, otherwise the client receives ciphertext.
"""
from __future__ import annotations

import io

import pytest

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"ENCRYPT-ME-PAYLOAD" * 24
_HEX_KEY = "1f" * 32  # 32-byte key as 64 hex chars


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def _encryption_on(monkeypatch):
    """Enable at-rest encryption for the duration of a test."""
    from app.core.config import get_settings

    monkeypatch.setenv("MATERIAL_ENCRYPTION_KEY", _HEX_KEY)
    monkeypatch.setenv("MATERIAL_ENCRYPTION_KEY_ID", "test-aes-gcm-v1")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_storage_roundtrip_ciphertext_on_disk(_encryption_on, tmp_path):
    from app.services import storage

    saved_root = storage._STORAGE_ROOT
    storage.reset_storage_root_for_tests(tmp_path)
    try:
        data = b"top-secret-passport-scan-bytes"
        stored = storage.store_bytes(42, "jpg", data)

        on_disk = (tmp_path / stored.storage_key).read_bytes()
        assert on_disk[:4] == b"HTX1", "file should be AES-GCM encrypted at rest"
        assert on_disk != data
        assert stored.encryption_key_id == "test-aes-gcm-v1"

        assert storage.read_bytes(stored.storage_key) == data
    finally:
        storage._STORAGE_ROOT = saved_root


async def _register(client, phone: str) -> str:
    email = f"{phone}@test.local"
    await client.post(
        "/api/v2/auth/register",
        json={
            "username": f"u{phone}",
            "email": email,
            "password": "Test1234",
            "email_code": "123456",
            "age_confirmed_16": True,
        },
    )
    r = await client.post("/api/v2/auth/login", json={"account": email, "password": "Test1234"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


class TestSignedUrlServesDecrypted:
    async def test_signed_url_returns_plaintext_when_encrypted(self, _encryption_on, client):
        token = await _register(client, "13911100001")
        files = {"file": ("enc.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        r = await client.post(
            "/api/v2/materials/upload",
            files=files,
            data={"material_type": "passport"},
            headers=_bearer(token),
        )
        assert r.status_code == 201, r.text
        url = r.json()["data"]["download_url"]

        served = await client.get(url)  # no bearer — HMAC token is the auth
        assert served.status_code == 200, served.text
        assert served.content == JPEG_BYTES, "serve endpoint must decrypt at-rest ciphertext"
