"""Registration verification email — i18n copy + HTML/plain renderers."""
from __future__ import annotations

from typing import Any

from app.email_templates._layout import (
    code_block,
    divider,
    email_shell,
    muted,
    paragraph,
    pick_locale,
)

EXPIRY_MINUTES = 10

_VERIFICATION_I18N: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Your HTEX verification code",
        "preheader": "Use this code to finish signing up. Expires in 10 minutes.",
        "title": "Welcome to HTEX",
        "intro": "You're almost there. Enter this verification code to complete your registration:",
        "expiry": "This code expires in 10 minutes.",
        "security": "If you didn't request this email, you can safely ignore it.",
        "tagline": "HTEX · Visa made clear",
        "footer": "This is an automated message. Please do not reply.",
    },
    "zh-CN": {
        "subject": "你的 HTEX 验证码",
        "preheader": "使用此验证码完成注册，10 分钟内有效。",
        "title": "欢迎加入 HTEX",
        "intro": "还差一步即可完成注册，请输入以下验证码：",
        "expiry": "验证码 10 分钟内有效。",
        "security": "如非本人操作，请忽略此邮件。",
        "tagline": "HTEX · 让签证办理更清晰",
        "footer": "本邮件由系统自动发送，请勿直接回复。",
    },
    "vi": {
        "subject": "Mã xác minh HTEX của bạn",
        "preheader": "Dùng mã này để hoàn tất đăng ký. Hết hạn sau 10 phút.",
        "title": "Chào mừng đến với HTEX",
        "intro": "Bạn sắp hoàn tất. Nhập mã xác minh sau để đăng ký:",
        "expiry": "Mã này hết hạn sau 10 phút.",
        "security": "Nếu bạn không yêu cầu email này, hãy bỏ qua.",
        "tagline": "HTEX · Visa rõ ràng hơn",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
    },
    "id": {
        "subject": "Kode verifikasi HTEX Anda",
        "preheader": "Gunakan kode ini untuk menyelesaikan pendaftaran. Berlaku 10 menit.",
        "title": "Selamat datang di HTEX",
        "intro": "Hampir selesai. Masukkan kode verifikasi berikut untuk mendaftar:",
        "expiry": "Kode ini kedaluwarsa dalam 10 menit.",
        "security": "Jika Anda tidak meminta email ini, abaikan saja.",
        "tagline": "HTEX · Visa lebih jelas",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
    },
}


def verification_strings(lang: str) -> dict[str, str]:
    return pick_locale(_VERIFICATION_I18N, lang)


def render_verification_plain(code: str, lang: str = "en") -> tuple[str, str]:
    t = verification_strings(lang)
    body = (
        f"{t['title']}\n\n"
        f"{t['intro']}\n\n"
        f"{code}\n\n"
        f"{t['expiry']}\n\n"
        f"{t['security']}\n\n"
        f"—\n{t['tagline']}\n{t['footer']}"
    )
    return t["subject"], body


def render_verification_html(code: str, lang: str = "en") -> str:
    t = verification_strings(lang)
    inner = (
        paragraph(t["intro"])
        + code_block(code)
        + muted(t["expiry"], margin_bottom=28)
        + divider()
        + muted(t["security"], margin_bottom=0)
    )
    return email_shell(
        lang=lang,
        subject=t["subject"],
        preheader=t["preheader"],
        title=t["title"],
        body_html=inner,
        tagline=t["tagline"],
        footer=t["footer"],
    )


def verification_i18n_for_preview() -> dict[str, Any]:
    return {"expiry_minutes": EXPIRY_MINUTES, "locales": _VERIFICATION_I18N}
