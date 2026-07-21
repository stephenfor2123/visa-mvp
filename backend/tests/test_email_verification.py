"""Unit tests for registration email verification template + send flow."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.email_templates.verification_code import render_verification_html, render_verification_plain
from app.services.email_service import (
    VerificationCodeEmail,
    send_verification_code_email,
)


class TestVerificationEmailTemplate:
    def test_subject_and_body_match_spec(self):
        subject, body = render_verification_plain("654321", "en")
        assert subject == "Your HTEX verification code"
        assert "Welcome to HTEX" in body
        assert "654321" in body
        assert "This code expires in 10 minutes." in body
        html = render_verification_html("654321", "zh-CN")
        assert "欢迎加入 HTEX" in html
        assert "1 2 3 4 5 6" in render_verification_html("123456", "en")


class TestSendVerificationEmailOutbox:
    async def test_outbox_writes_from_and_template(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        outbox = tmp_path / "email_outbox"
        outbox.mkdir()
        monkeypatch.setattr(
            "app.services.email_service._outbox_dir",
            lambda: outbox,
        )

        ok = send_verification_code_email(
            VerificationCodeEmail(to_email="dev@htexvisa.com", code="654321"),
        )
        assert ok is True
        files = list(outbox.glob("*.eml"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "From: HTEX <noreply@htexvisa.com>" in content
        assert "Subject: Your HTEX verification code" in content
        assert "Welcome to HTEX" in content
        assert "654321" in content
        assert "This code expires in 10 minutes." in content


class TestSendEmailCodeEndpoint:
    async def test_send_email_code_happy(self, client):
        r = await client.post(
            "/api/v2/auth/send-email-code",
            json={"email": "newuser@htex.test", "purpose": "register"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == "1000"
        assert body["data"]["email"] == "newuser@htex.test"
        assert body["data"]["expires_in"] == 600
        assert body["data"]["code"]  # outbox/dev echo

    async def test_send_email_code_rejects_registered_email(self, client):
        await client.post(
            "/api/v2/auth/send-email-code",
            json={"email": "taken@htex.test", "purpose": "register"},
        )
        await client.post(
            "/api/v2/auth/register",
            json={
                "username": "takenuser",
                "email": "taken@htex.test",
                "password": "abc12345",
                "email_code": "123456",
                "age_confirmed_16": True,
            },
        )
        r = await client.post(
            "/api/v2/auth/send-email-code",
            json={"email": "taken@htex.test", "purpose": "register"},
        )
        assert r.status_code == 409
        assert r.json()["code"] == "2003"

    async def test_register_with_sent_code(self, client):
        send = await client.post(
            "/api/v2/auth/send-email-code",
            json={"email": "coded@htex.test", "purpose": "register"},
        )
        code = send.json()["data"]["code"]
        r = await client.post(
            "/api/v2/auth/register",
            json={
                "username": "codeduser",
                "email": "coded@htex.test",
                "password": "abc12345",
                "email_code": code,
                "age_confirmed_16": True,
            },
        )
        assert r.status_code == 201, r.text
