"""
Email service stub — W48.

Goal:
  让"注册成功 → 发欢迎邮件"这条链路可以在 MVP 阶段跑通 + 留 audit，
  又不在没有外部 SMTP / Resend key 的情况下报错打断注册流程。

实现策略：
  - 默认（无 SMTP 配置）→ 把渲染好的 .eml 写到 logs/email_outbox/{ts}_{user_id}.eml，
    并在日志里 INFO 一行（审计可见、可调试）。
  - 后续接 SMTP / Resend / Mailgun 时只要加一个新 backend，把这里 if/else 替换掉。
    渲染（template）和 dispatch 解耦，方便复用。

注意：
  - 永远不让发邮件失败冒泡到主流程（catch + log.warning）。
  - 邮件模板用纯字符串 + .format，不要拉 jinja2（依赖越少越好）。
  - 模板保留 {nickname}/{email}/{login_url} 占位符。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WelcomeEmail:
    to_email: str
    nickname: str
    username: str
    language_pref: str  # 'zh-CN' | 'en' | 'vi' | 'id' ...


# ---------------------------------------------------------------------------
# 模板（按语言; fallback 到 en）
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict[str, str]] = {
    "zh-CN": {
        "subject": "欢迎加入 Htex — 你的签证管家",
        "title": "欢迎加入 Htex",
        "greeting": "{nickname} 你好，",
        "intro": "感谢你注册 Htex 账号。从今天起，签证办理从此变得清晰、可追踪。",
        "step1_title": "选国家",
        "step1_desc": "告诉你要去哪里，我们立即生成对应的材料清单。",
        "step2_title": "看清单",
        "step2_desc": "每一项材料都附带要求说明与参考样本。",
        "step3_title": "OCR 上传",
        "step3_desc": "拍照自动识别字段，省去手动填写。",
        "cta": "立即开始",
        "footer": "本邮件由系统自动发送，请勿回复。",
        "signature": "— Htex 团队",
    },
    "en": {
        "subject": "Welcome to Htex — your visa companion",
        "title": "Welcome to Htex",
        "greeting": "Hi {nickname},",
        "intro": "Thanks for signing up for Htex. From today on, visa applications become clear and trackable.",
        "step1_title": "Pick a country",
        "step1_desc": "Tell us where you're going, and we instantly generate the matching document checklist.",
        "step2_title": "View the checklist",
        "step2_desc": "Each item comes with requirement notes and reference samples.",
        "step3_title": "OCR upload",
        "step3_desc": "Snap a photo and the fields auto-fill — no more manual entry.",
        "cta": "Get started",
        "footer": "This is an automated message, please do not reply.",
        "signature": "— The Htex team",
    },
    "vi": {
        "subject": "Chào mừng bạn đến với Htex",
        "title": "Chào mừng bạn đến với Htex",
        "greeting": "Xin chào {nickname},",
        "intro": "Cảm ơn bạn đã đăng ký Htex. Từ hôm nay, thủ tục visa trở nên rõ ràng và có thể theo dõi.",
        "step1_title": "Chọn quốc gia",
        "step1_desc": "Cho chúng tôi biết bạn muốn đi đâu, chúng tôi sẽ tạo danh sách tài liệu ngay.",
        "step2_title": "Xem danh sách",
        "step2_desc": "Mỗi mục đều có ghi chú yêu cầu và mẫu tham khảo.",
        "step3_title": "Tải lên bằng OCR",
        "step3_desc": "Chụp ảnh và các trường tự động điền.",
        "cta": "Bắt đầu ngay",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
        "signature": "— Đội ngũ Htex",
    },
    "id": {
        "subject": "Selamat datang di Htex",
        "title": "Selamat datang di Htex",
        "greeting": "Halo {nickname},",
        "intro": "Terima kasih telah mendaftar Htex. Mulai hari ini, pengajuan visa jadi jelas dan terlacak.",
        "step1_title": "Pilih negara",
        "step1_desc": "Beri tahu kami tujuan Anda, kami langsung buat daftar dokumen.",
        "step2_title": "Lihat daftar",
        "step2_desc": "Setiap item disertai catatan syarat dan contoh referensi.",
        "step3_title": "Unggah OCR",
        "step3_desc": "Foto dokumen dan kolom terisi otomatis.",
        "cta": "Mulai sekarang",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
        "signature": "— Tim Htex",
    },
}


def _template_for(lang: str) -> dict[str, str]:
    return _TEMPLATES.get(lang) or _TEMPLATES.get((lang or "").split("-")[0]) or _TEMPLATES["en"]


def render_welcome(msg: WelcomeEmail, login_url: str = "") -> str:
    """Render a welcome email as a multipart-ish plain string (subject + body)."""
    tpl = _template_for(msg.language_pref)
    nickname = msg.nickname or msg.username or "there"
    body = (
        f"{tpl['title']}\n"
        f"{'=' * len(tpl['title'])}\n\n"
        f"{tpl['greeting'].format(nickname=nickname)}\n\n"
        f"{tpl['intro']}\n\n"
        f"  1. {tpl['step1_title']} — {tpl['step1_desc']}\n"
        f"  2. {tpl['step2_title']} — {tpl['step2_desc']}\n"
        f"  3. {tpl['step3_title']} — {tpl['step3_desc']}\n\n"
        f"{tpl['cta']}: {login_url or 'https://htex.app'}\n\n"
        f"—\n{tpl['footer']}\n{tpl['signature']}\n"
    )
    return f"Subject: {tpl['subject']}\nTo: {msg.to_email}\n\n{body}"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _outbox_dir() -> Path:
    """Return (and ensure) the outbox directory. Lives at <repo>/logs/email_outbox."""
    repo_root = Path(__file__).resolve().parents[3]  # backend/app/services/ → repo root
    out = repo_root / "logs" / "email_outbox"
    out.mkdir(parents=True, exist_ok=True)
    return out


def send_welcome_email(msg: WelcomeEmail, login_url: str = "") -> bool:
    """
    Dispatch the rendered welcome email. Never raises.

    Returns True on best-effort success, False otherwise.
    Future: branch on settings.email_backend == 'smtp' | 'resend' to pick the real sender.
    """
    try:
        rendered = render_welcome(msg, login_url=login_url)
        out_dir = _outbox_dir()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        # user_id 还没出来(user 还没 commit), 这里退化为 username hash 占位,
        # 实际写入时由 caller 决定是否覆盖文件名。
        safe_user = (msg.username or msg.to_email.split("@")[0] or "user").replace(os.sep, "_")
        fname = f"{stamp}_welcome_{safe_user}.eml"
        target = out_dir / fname
        target.write_text(rendered, encoding="utf-8")
        _log.info(
            "email.welcome.sent",
            extra={
                "event_type": "email.welcome.sent",
                "to": msg.to_email,
                "lang": msg.language_pref,
                "backend": "outbox",
                "path": str(target),
            },
        )
        return True
    except Exception as exc:  # pragma: no cover — defensive
        _log.warning(
            "email.welcome.failed",
            extra={
                "event_type": "email.welcome.failed",
                "to": msg.to_email,
                "error": str(exc),
            },
        )
        return False


# ---------------------------------------------------------------------------
# W1 — Email change verification
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EmailChangeVerification:
    to_email: str
    nickname: str
    language_pref: str
    confirm_url: str  # full URL with embedded token


_EMAIL_CHANGE_TEMPLATES: dict[str, dict[str, str]] = {
    "zh-CN": {
        "subject": "请确认你的新邮箱地址 — Htex",
        "title": "确认新邮箱",
        "greeting": "{nickname} 你好，",
        "intro": "你正在将 Htex 账号的邮箱更换为 {new_email}。请点击下方按钮完成确认：",
        "cta": "确认新邮箱",
        "expiry": "该链接 30 分钟内有效，如非本人操作请忽略本邮件。",
        "footer": "本邮件由系统自动发送，请勿回复。",
        "signature": "— Htex 团队",
    },
    "en": {
        "subject": "Confirm your new email — Htex",
        "title": "Confirm new email",
        "greeting": "Hi {nickname},",
        "intro": "You are changing the email on your Htex account to {new_email}. Click the button below to confirm:",
        "cta": "Confirm new email",
        "expiry": "This link expires in 30 minutes. If you didn't request this, ignore this email.",
        "footer": "This is an automated message, please do not reply.",
        "signature": "— The Htex team",
    },
    "vi": {
        "subject": "Xác nhận email mới của bạn — Htex",
        "title": "Xác nhận email mới",
        "greeting": "Xin chào {nickname},",
        "intro": "Bạn đang thay đổi email tài khoản Htex thành {new_email}. Nhấp vào nút bên dưới để xác nhận:",
        "cta": "Xác nhận email mới",
        "expiry": "Liên kết hết hạn sau 30 phút. Nếu bạn không yêu cầu, vui lòng bỏ qua email này.",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
        "signature": "— Đội ngũ Htex",
    },
    "id": {
        "subject": "Konfirmasi email baru Anda — Htex",
        "title": "Konfirmasi email baru",
        "greeting": "Halo {nickname},",
        "intro": "Anda sedang mengubah email akun Htex menjadi {new_email}. Klik tombol di bawah untuk konfirmasi:",
        "cta": "Konfirmasi email baru",
        "expiry": "Tautan kedaluwarsa dalam 30 menit. Jika bukan Anda yang meminta, abaikan email ini.",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
        "signature": "— Tim Htex",
    },
}


def _email_change_template_for(lang: str) -> dict[str, str]:
    return _EMAIL_CHANGE_TEMPLATES.get(lang) or _EMAIL_CHANGE_TEMPLATES.get((lang or "").split("-")[0]) or _EMAIL_CHANGE_TEMPLATES["en"]


def render_email_change(msg: EmailChangeVerification, new_email: str) -> str:
    tpl = _email_change_template_for(msg.language_pref)
    nickname = msg.nickname or "there"
    body = (
        f"{tpl['title']}\n"
        f"{'=' * len(tpl['title'])}\n\n"
        f"{tpl['greeting'].format(nickname=nickname)}\n\n"
        f"{tpl['intro'].format(new_email=new_email)}\n\n"
        f"  {tpl['cta']}: {msg.confirm_url}\n\n"
        f"{tpl['expiry']}\n\n"
        f"—\n{tpl['footer']}\n{tpl['signature']}\n"
    )
    return f"Subject: {tpl['subject']}\nTo: {msg.to_email}\n\n{body}"


def send_email_change_verification(msg: EmailChangeVerification, new_email: str) -> bool:
    """Best-effort dispatch. Never raises. Returns True on success."""
    try:
        rendered = render_email_change(msg, new_email=new_email)
        out_dir = _outbox_dir()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        safe_to = (msg.to_email.split("@")[0] or "user").replace(os.sep, "_")
        fname = f"{stamp}_email_change_{safe_to}.eml"
        target = out_dir / fname
        target.write_text(rendered, encoding="utf-8")
        _log.info(
            "email.change.verification.sent",
            extra={
                "event_type": "email.change.verification.sent",
                "to": msg.to_email,
                "lang": msg.language_pref,
                "backend": "outbox",
                "path": str(target),
            },
        )
        return True
    except Exception as exc:  # pragma: no cover — defensive
        _log.warning(
            "email.change.verification.failed",
            extra={
                "event_type": "email.change.verification.failed",
                "to": msg.to_email,
                "error": str(exc),
            },
        )
        return False


# ---------------------------------------------------------------------------
# Password reset (email token)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PasswordResetEmail:
    to_email: str
    nickname: str
    language_pref: str
    reset_url: str


_PASSWORD_RESET_TEMPLATES: dict[str, dict[str, str]] = {
    "zh-CN": {
        "subject": "重置你的 Htex 密码",
        "title": "重置密码",
        "greeting": "{nickname} 你好，",
        "intro": "我们收到了重置你 Htex 账号密码的请求。请点击下方链接设置新密码：",
        "cta": "重置密码",
        "expiry": "该链接 30 分钟内有效。如非本人操作，请忽略本邮件。",
        "footer": "本邮件由系统自动发送，请勿回复。",
        "signature": "— Htex 团队",
    },
    "en": {
        "subject": "Reset your Htex password",
        "title": "Reset password",
        "greeting": "Hi {nickname},",
        "intro": "We received a request to reset the password on your Htex account. Click the link below to set a new password:",
        "cta": "Reset password",
        "expiry": "This link expires in 30 minutes. If you didn't request this, ignore this email.",
        "footer": "This is an automated message, please do not reply.",
        "signature": "— The Htex team",
    },
    "vi": {
        "subject": "Đặt lại mật khẩu Htex của bạn",
        "title": "Đặt lại mật khẩu",
        "greeting": "Xin chào {nickname},",
        "intro": "Chúng tôi nhận được yêu cầu đặt lại mật khẩu tài khoản Htex của bạn. Nhấp vào liên kết bên dưới:",
        "cta": "Đặt lại mật khẩu",
        "expiry": "Liên kết hết hạn sau 30 phút. Nếu không phải bạn, vui lòng bỏ qua.",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
        "signature": "— Đội ngũ Htex",
    },
    "id": {
        "subject": "Atur ulang kata sandi Htex Anda",
        "title": "Atur ulang kata sandi",
        "greeting": "Halo {nickname},",
        "intro": "Kami menerima permintaan untuk mengatur ulang kata sandi akun Htex Anda. Klik tautan di bawah:",
        "cta": "Atur ulang kata sandi",
        "expiry": "Tautan kedaluwarsa dalam 30 menit. Jika bukan Anda, abaikan email ini.",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
        "signature": "— Tim Htex",
    },
}


def _password_reset_template_for(lang: str) -> dict[str, str]:
    return _PASSWORD_RESET_TEMPLATES.get(lang) or _PASSWORD_RESET_TEMPLATES.get((lang or "").split("-")[0]) or _PASSWORD_RESET_TEMPLATES["en"]


def render_password_reset(msg: PasswordResetEmail) -> str:
    tpl = _password_reset_template_for(msg.language_pref)
    nickname = msg.nickname or "there"
    body = (
        f"{tpl['title']}\n"
        f"{'=' * len(tpl['title'])}\n\n"
        f"{tpl['greeting'].format(nickname=nickname)}\n\n"
        f"{tpl['intro']}\n\n"
        f"  {tpl['cta']}: {msg.reset_url}\n\n"
        f"{tpl['expiry']}\n\n"
        f"—\n{tpl['footer']}\n{tpl['signature']}\n"
    )
    return f"Subject: {tpl['subject']}\nTo: {msg.to_email}\n\n{body}"


def send_password_reset_email(msg: PasswordResetEmail) -> bool:
    """Best-effort dispatch. Never raises."""
    try:
        rendered = render_password_reset(msg)
        out_dir = _outbox_dir()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        safe_to = (msg.to_email.split("@")[0] or "user").replace(os.sep, "_")
        fname = f"{stamp}_password_reset_{safe_to}.eml"
        target = out_dir / fname
        target.write_text(rendered, encoding="utf-8")
        _log.info(
            "email.password_reset.sent",
            extra={
                "event_type": "email.password_reset.sent",
                "to": msg.to_email,
                "lang": msg.language_pref,
                "backend": "outbox",
                "path": str(target),
            },
        )
        return True
    except Exception as exc:  # pragma: no cover
        _log.warning(
            "email.password_reset.failed",
            extra={
                "event_type": "email.password_reset.failed",
                "to": msg.to_email,
                "error": str(exc),
            },
        )
        return False