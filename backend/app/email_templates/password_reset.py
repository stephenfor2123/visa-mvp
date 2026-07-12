"""Forgot password — reset link email."""
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
        "subject": "Reset your HTEX password",
        "preheader": "Reset your password. This link expires in 30 minutes.",
        "title": "Reset your password",
        "greeting": "Hi {nickname},",
        "intro": "We received a request to reset the password on your HTEX account. Click the button below to set a new password:",
        "cta": "Reset password",
        "expiry": "This link expires in 30 minutes.",
        "security": "If you didn't request a password reset, you can safely ignore this email. Your password will stay the same.",
        "link_label": "Or copy this link into your browser:",
        "tagline": "HTEX · Visa made clear",
        "footer": "This is an automated message. Please do not reply.",
    },
    "zh-CN": {
        "subject": "重置你的 HTEX 密码",
        "preheader": "点击链接重置密码，30 分钟内有效。",
        "title": "重置密码",
        "greeting": "{nickname} 你好，",
        "intro": "我们收到了重置你 HTEX 账号密码的请求。请点击下方按钮设置新密码：",
        "cta": "重置密码",
        "expiry": "该链接 30 分钟内有效。",
        "security": "如非本人操作，请忽略此邮件，你的密码将保持不变。",
        "link_label": "或复制以下链接到浏览器打开：",
        "tagline": "HTEX · 让签证办理更清晰",
        "footer": "本邮件由系统自动发送，请勿直接回复。",
    },
    "vi": {
        "subject": "Đặt lại mật khẩu HTEX",
        "preheader": "Đặt lại mật khẩu. Liên kết hết hạn sau 30 phút.",
        "title": "Đặt lại mật khẩu",
        "greeting": "Xin chào {nickname},",
        "intro": "Chúng tôi nhận được yêu cầu đặt lại mật khẩu tài khoản HTEX của bạn. Nhấp nút bên dưới:",
        "cta": "Đặt lại mật khẩu",
        "expiry": "Liên kết hết hạn sau 30 phút.",
        "security": "Nếu bạn không yêu cầu, hãy bỏ qua email này. Mật khẩu của bạn sẽ không thay đổi.",
        "link_label": "Hoặc sao chép liên kết sau vào trình duyệt:",
        "tagline": "HTEX · Visa rõ ràng hơn",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
    },
    "id": {
        "subject": "Atur ulang kata sandi HTEX",
        "preheader": "Atur ulang kata sandi. Tautan berlaku 30 menit.",
        "title": "Atur ulang kata sandi",
        "greeting": "Halo {nickname},",
        "intro": "Kami menerima permintaan untuk mengatur ulang kata sandi akun HTEX Anda. Klik tombol di bawah:",
        "cta": "Atur ulang kata sandi",
        "expiry": "Tautan kedaluwarsa dalam 30 menit.",
        "security": "Jika bukan Anda yang meminta, abaikan email ini. Kata sandi Anda tidak akan berubah.",
        "link_label": "Atau salin tautan berikut ke browser:",
        "tagline": "HTEX · Visa lebih jelas",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
    },
}


def render_password_reset_plain(
    *, nickname: str, reset_url: str, lang: str = "en"
) -> tuple[str, str]:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    body = (
        f"{t['greeting'].format(nickname=nick)}\n\n"
        f"{t['intro']}\n\n"
        f"{reset_url}\n\n"
        f"{t['expiry']}\n\n"
        f"{t['security']}\n\n"
        f"—\n{t['tagline']}\n{t['footer']}"
    )
    return t["subject"], body


def render_password_reset_html(
    *, nickname: str, reset_url: str, lang: str = "en"
) -> str:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    inner = (
        paragraph(t["greeting"].format(nickname=nick), margin_bottom=12)
        + paragraph(t["intro"])
        + cta_button(reset_url, t["cta"])
        + muted(t["link_label"], margin_bottom=8)
        + link_fallback(reset_url)
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
