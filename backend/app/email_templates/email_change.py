"""Email address change — confirmation link to new inbox."""
from __future__ import annotations

from app.email_templates._layout import (
    cta_button,
    divider,
    email_shell,
    link_fallback,
    muted,
    paragraph,
    pick_locale,
)

EXPIRY_MINUTES = 30

_I18N: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Confirm your new HTEX email",
        "preheader": "Confirm your new email address. Link expires in 30 minutes.",
        "title": "Confirm new email",
        "greeting": "Hi {nickname},",
        "intro": "You requested to change the email on your HTEX account to:",
        "email_highlight": "{new_email}",
        "cta": "Confirm new email",
        "expiry": "This link expires in 30 minutes.",
        "security": "If you didn't request this change, ignore this email and your account email will stay the same.",
        "link_label": "Or copy this link into your browser:",
        "tagline": "HTEX · Visa made clear",
        "footer": "This is an automated message. Please do not reply.",
    },
    "zh-CN": {
        "subject": "确认你的新 HTEX 邮箱",
        "preheader": "确认新邮箱地址，链接 30 分钟内有效。",
        "title": "确认新邮箱",
        "greeting": "{nickname} 你好，",
        "intro": "你申请将 HTEX 账号邮箱更换为：",
        "email_highlight": "{new_email}",
        "cta": "确认新邮箱",
        "expiry": "该链接 30 分钟内有效。",
        "security": "如非本人操作，请忽略此邮件，你的账号邮箱将保持不变。",
        "link_label": "或复制以下链接到浏览器打开：",
        "tagline": "HTEX · 让签证办理更清晰",
        "footer": "本邮件由系统自动发送，请勿直接回复。",
    },
    "vi": {
        "subject": "Xác nhận email HTEX mới",
        "preheader": "Xác nhận email mới. Liên kết hết hạn sau 30 phút.",
        "title": "Xác nhận email mới",
        "greeting": "Xin chào {nickname},",
        "intro": "Bạn yêu cầu đổi email tài khoản HTEX thành:",
        "email_highlight": "{new_email}",
        "cta": "Xác nhận email mới",
        "expiry": "Liên kết hết hạn sau 30 phút.",
        "security": "Nếu không phải bạn, hãy bỏ qua email này.",
        "link_label": "Hoặc sao chép liên kết sau:",
        "tagline": "HTEX · Visa rõ ràng hơn",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
    },
    "id": {
        "subject": "Konfirmasi email HTEX baru",
        "preheader": "Konfirmasi email baru. Tautan berlaku 30 menit.",
        "title": "Konfirmasi email baru",
        "greeting": "Halo {nickname},",
        "intro": "Anda meminta mengubah email akun HTEX menjadi:",
        "email_highlight": "{new_email}",
        "cta": "Konfirmasi email baru",
        "expiry": "Tautan kedaluwarsa dalam 30 menit.",
        "security": "Jika bukan Anda, abaikan email ini.",
        "link_label": "Atau salin tautan berikut:",
        "tagline": "HTEX · Visa lebih jelas",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
    },
}


def _email_highlight_html(new_email: str, template: str) -> str:
    from html import escape

    return (
        f'<p style="margin:0 0 28px;font-size:16px;line-height:24px;font-weight:600;'
        f'color:#0F172A;">{escape(template.format(new_email=new_email))}</p>'
    )


def render_email_change_plain(
    *, nickname: str, new_email: str, confirm_url: str, lang: str = "en"
) -> tuple[str, str]:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    body = (
        f"{t['greeting'].format(nickname=nick)}\n\n"
        f"{t['intro']}\n"
        f"{new_email}\n\n"
        f"{confirm_url}\n\n"
        f"{t['expiry']}\n\n"
        f"{t['security']}\n\n"
        f"—\n{t['tagline']}\n{t['footer']}"
    )
    return t["subject"], body


def render_email_change_html(
    *, nickname: str, new_email: str, confirm_url: str, lang: str = "en"
) -> str:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    inner = (
        paragraph(t["greeting"].format(nickname=nick), margin_bottom=12)
        + paragraph(t["intro"], margin_bottom=8)
        + _email_highlight_html(new_email, t["email_highlight"])
        + cta_button(confirm_url, t["cta"])
        + muted(t["link_label"], margin_bottom=8)
        + link_fallback(confirm_url)
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
