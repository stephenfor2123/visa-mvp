"""Password changed confirmation — sent after a successful password update."""
from __future__ import annotations

from app.email_templates._layout import (
    cta_button,
    divider,
    email_shell,
    muted,
    paragraph,
    pick_locale,
    success_banner,
)

_I18N: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Your HTEX password was updated",
        "preheader": "Your account password was changed successfully.",
        "title": "Password updated",
        "greeting": "Hi {nickname},",
        "banner": "Your password has been changed successfully.",
        "intro": "This is a confirmation that the password on your HTEX account was just updated. All other active sessions have been signed out for your security.",
        "cta": "Sign in again",
        "security": "If you did not make this change, reset your password immediately and contact support.",
        "tagline": "HTEX · Visa made clear",
        "footer": "This is an automated message. Please do not reply.",
    },
    "zh-CN": {
        "subject": "你的 HTEX 密码已更新",
        "preheader": "你的账号密码已成功修改。",
        "title": "密码已更新",
        "greeting": "{nickname} 你好，",
        "banner": "你的密码已成功修改。",
        "intro": "此邮件用于确认你的 HTEX 账号密码刚刚已更新。为保障安全，其他已登录的设备/session 已自动退出。",
        "cta": "重新登录",
        "security": "如非本人操作，请立即重置密码并联系客服。",
        "tagline": "HTEX · 让签证办理更清晰",
        "footer": "本邮件由系统自动发送，请勿直接回复。",
    },
    "vi": {
        "subject": "Mật khẩu HTEX của bạn đã được cập nhật",
        "preheader": "Mật khẩu tài khoản đã được thay đổi thành công.",
        "title": "Mật khẩu đã cập nhật",
        "greeting": "Xin chào {nickname},",
        "banner": "Mật khẩu của bạn đã được thay đổi thành công.",
        "intro": "Email này xác nhận mật khẩu tài khoản HTEX vừa được cập nhật. Các phiên đăng nhập khác đã được đăng xuất để bảo mật.",
        "cta": "Đăng nhập lại",
        "security": "Nếu không phải bạn, hãy đặt lại mật khẩu ngay và liên hệ hỗ trợ.",
        "tagline": "HTEX · Visa rõ ràng hơn",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
    },
    "id": {
        "subject": "Kata sandi HTEX Anda telah diperbarui",
        "preheader": "Kata sandi akun berhasil diubah.",
        "title": "Kata sandi diperbarui",
        "greeting": "Halo {nickname},",
        "banner": "Kata sandi Anda berhasil diubah.",
        "intro": "Email ini mengonfirmasi kata sandi akun HTEX Anda baru saja diperbarui. Sesi aktif lainnya telah keluar demi keamanan.",
        "cta": "Masuk kembali",
        "security": "Jika bukan Anda, segera atur ulang kata sandi dan hubungi dukungan.",
        "tagline": "HTEX · Visa lebih jelas",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
    },
}


def render_password_changed_plain(
    *, nickname: str, login_url: str, lang: str = "en"
) -> tuple[str, str]:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    body = (
        f"{t['greeting'].format(nickname=nick)}\n\n"
        f"{t['banner']}\n\n"
        f"{t['intro']}\n\n"
        f"{login_url}\n\n"
        f"{t['security']}\n\n"
        f"—\n{t['tagline']}\n{t['footer']}"
    )
    return t["subject"], body


def render_password_changed_html(
    *, nickname: str, login_url: str, lang: str = "en"
) -> str:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    inner = (
        paragraph(t["greeting"].format(nickname=nick), margin_bottom=12)
        + success_banner(t["banner"])
        + paragraph(t["intro"])
        + cta_button(login_url, t["cta"])
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
