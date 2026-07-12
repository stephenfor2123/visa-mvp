"""
Email dispatch — Resend (prod) or outbox stub (dev).

Templates live in ``app.email_templates.*``; this module only dispatches.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.email_templates.email_change import render_email_change_html, render_email_change_plain
from app.email_templates.password_changed import (
    render_password_changed_html,
    render_password_changed_plain,
)
from app.email_templates.password_reset import render_password_reset_html, render_password_reset_plain
from app.email_templates.verification_code import render_verification_html, render_verification_plain
from app.email_templates.welcome import render_welcome_html, render_welcome_plain

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WelcomeEmail:
    to_email: str
    nickname: str
    username: str
    language_pref: str


@dataclass(frozen=True)
class VerificationCodeEmail:
    to_email: str
    code: str
    language_pref: str = "en"


@dataclass(frozen=True)
class EmailChangeVerification:
    to_email: str
    nickname: str
    language_pref: str
    confirm_url: str


@dataclass(frozen=True)
class PasswordResetEmail:
    to_email: str
    nickname: str
    language_pref: str
    reset_url: str


@dataclass(frozen=True)
class PasswordChangedEmail:
    to_email: str
    nickname: str
    language_pref: str
    login_url: str


def render_verification_code(msg: VerificationCodeEmail) -> tuple[str, str, str]:
    subject, text = render_verification_plain(msg.code, msg.language_pref)
    return subject, text, render_verification_html(msg.code, msg.language_pref)


def _outbox_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    out = repo_root / "logs" / "email_outbox"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _dispatch_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
    log_event: str,
    outbox_prefix: str,
) -> bool:
    settings = get_settings()
    try:
        if settings.email_backend == "resend":
            import httpx

            payload: dict[str, object] = {
                "from": settings.email_from,
                "to": [to_email],
                "subject": subject,
                "text": body,
            }
            if html:
                payload["html"] = html
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
            backend = "resend"
            path = resp.json().get("id", "sent")
        else:
            rendered = f"From: {settings.email_from}\nSubject: {subject}\nTo: {to_email}\n\n{body}"
            if html:
                rendered += f"\n\n--- HTML ---\n{html}"
            out_dir = _outbox_dir()
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            safe_to = (to_email.split("@")[0] or "user").replace(os.sep, "_")
            target = out_dir / f"{stamp}_{outbox_prefix}_{safe_to}.eml"
            target.write_text(rendered, encoding="utf-8")
            backend = "outbox"
            path = str(target)

        _log.info(
            log_event,
            extra={
                "event_type": log_event,
                "to": to_email,
                "backend": backend,
                "path": path,
            },
        )
        return True
    except Exception as exc:  # pragma: no cover
        _log.warning(
            f"{log_event}.failed",
            extra={
                "event_type": f"{log_event}.failed",
                "to": to_email,
                "error": str(exc),
            },
        )
        return False


def send_verification_code_email(msg: VerificationCodeEmail) -> bool:
    subject, text, html = render_verification_code(msg)
    return _dispatch_email(
        to_email=msg.to_email,
        subject=subject,
        body=text,
        html=html,
        log_event="email.verification_code.sent",
        outbox_prefix="verification_code",
    )


def send_welcome_email(msg: WelcomeEmail, login_url: str = "") -> bool:
    url = login_url or get_settings().app_frontend_base or "https://htex.app"
    nick = msg.nickname or msg.username or "there"
    subject, text = render_welcome_plain(nickname=nick, login_url=url, lang=msg.language_pref)
    html = render_welcome_html(nickname=nick, login_url=url, lang=msg.language_pref)
    return _dispatch_email(
        to_email=msg.to_email,
        subject=subject,
        body=text,
        html=html,
        log_event="email.welcome.sent",
        outbox_prefix="welcome",
    )


def send_email_change_verification(msg: EmailChangeVerification, new_email: str) -> bool:
    nick = msg.nickname or "there"
    subject, text = render_email_change_plain(
        nickname=nick,
        new_email=new_email,
        confirm_url=msg.confirm_url,
        lang=msg.language_pref,
    )
    html = render_email_change_html(
        nickname=nick,
        new_email=new_email,
        confirm_url=msg.confirm_url,
        lang=msg.language_pref,
    )
    return _dispatch_email(
        to_email=msg.to_email,
        subject=subject,
        body=text,
        html=html,
        log_event="email.change.verification.sent",
        outbox_prefix="email_change",
    )


def send_password_reset_email(msg: PasswordResetEmail) -> bool:
    nick = msg.nickname or "there"
    subject, text = render_password_reset_plain(
        nickname=nick, reset_url=msg.reset_url, lang=msg.language_pref
    )
    html = render_password_reset_html(
        nickname=nick, reset_url=msg.reset_url, lang=msg.language_pref
    )
    return _dispatch_email(
        to_email=msg.to_email,
        subject=subject,
        body=text,
        html=html,
        log_event="email.password_reset.sent",
        outbox_prefix="password_reset",
    )


def send_password_changed_email(msg: PasswordChangedEmail) -> bool:
    nick = msg.nickname or "there"
    subject, text = render_password_changed_plain(
        nickname=nick, login_url=msg.login_url, lang=msg.language_pref
    )
    html = render_password_changed_html(
        nickname=nick, login_url=msg.login_url, lang=msg.language_pref
    )
    return _dispatch_email(
        to_email=msg.to_email,
        subject=subject,
        body=text,
        html=html,
        log_event="email.password_changed.sent",
        outbox_prefix="password_changed",
    )
