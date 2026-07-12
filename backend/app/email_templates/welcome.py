"""Welcome email — sent after successful registration."""
from __future__ import annotations

from app.email_templates._layout import (
    cta_button,
    email_shell,
    paragraph,
    pick_locale,
    steps_list,
)

_I18N: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Welcome to HTEX",
        "preheader": "Your account is ready. Start your visa application in 3 steps.",
        "title": "Welcome to HTEX",
        "greeting": "Hi {nickname},",
        "intro": "Thanks for signing up. From today on, visa applications become clear and easier to track.",
        "step1_title": "Your checklist",
        "step1_desc": "Pick destination — we build your list.",
        "step2_title": "Snap & pre-check",
        "step2_desc": "OCR upload, catch gaps early.",
        "step3_title": "Submit faster",
        "step3_desc": "Forms + translation, less hassle.",
        "cta": "Get started",
        "tagline": "HTEX · Visa made clear",
        "footer": "This is an automated message. Please do not reply.",
    },
    "zh-CN": {
        "subject": "欢迎加入 HTEX",
        "preheader": "账号已就绪，3 步开始你的签证办理。",
        "title": "欢迎加入 HTEX",
        "greeting": "{nickname} 你好，",
        "intro": "感谢你注册 HTEX。让签证办理更清晰、可追踪。",
        "step1_title": "专属清单",
        "step1_desc": "选目的地，即时出清单",
        "step2_title": "拍照预审",
        "step2_desc": "上传识别，查缺漏风险",
        "step3_title": "跨语提交",
        "step3_desc": "填表翻译，更快更简单",
        "cta": "立即开始",
        "tagline": "HTEX · 让签证办理更清晰",
        "footer": "本邮件由系统自动发送，请勿直接回复。",
    },
    "vi": {
        "subject": "Chào mừng đến với HTEX",
        "preheader": "Tài khoản đã sẵn sàng. Bắt đầu hồ sơ visa trong 3 bước.",
        "title": "Chào mừng đến với HTEX",
        "greeting": "Xin chào {nickname},",
        "intro": "Cảm ơn bạn đã đăng ký. Hồ sơ visa rõ ràng và dễ theo dõi hơn.",
        "step1_title": "Danh sách riêng",
        "step1_desc": "Chọn điểm đến, tạo list ngay.",
        "step2_title": "Chụp & kiểm tra",
        "step2_desc": "OCR tải lên, phát hiện lỗi.",
        "step3_title": "Nộp nhanh",
        "step3_desc": "Điền form + dịch, đơn giản.",
        "cta": "Bắt đầu ngay",
        "tagline": "HTEX · Visa rõ ràng hơn",
        "footer": "Đây là email tự động, vui lòng không trả lời.",
    },
    "id": {
        "subject": "Selamat datang di HTEX",
        "preheader": "Akun siap. Mulai visa Anda dalam 3 langkah.",
        "title": "Selamat datang di HTEX",
        "greeting": "Halo {nickname},",
        "intro": "Terima kasih telah mendaftar. Pengajuan visa jadi lebih jelas dan terlacak.",
        "step1_title": "Daftar khusus",
        "step1_desc": "Pilih tujuan, buat list.",
        "step2_title": "Foto & cek",
        "step2_desc": "OCR unggah, deteksi celah.",
        "step3_title": "Ajukan cepat",
        "step3_desc": "Isi form + terjemah, mudah.",
        "cta": "Mulai sekarang",
        "tagline": "HTEX · Visa lebih jelas",
        "footer": "Email ini dibuat otomatis, mohon tidak dibalas.",
    },
}


def render_welcome_plain(
    *, nickname: str, login_url: str, lang: str = "en"
) -> tuple[str, str]:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    body = (
        f"{t['greeting'].format(nickname=nick)}\n\n"
        f"{t['intro']}\n\n"
        f"1. {t['step1_title']} — {t['step1_desc']}\n"
        f"2. {t['step2_title']} — {t['step2_desc']}\n"
        f"3. {t['step3_title']} — {t['step3_desc']}\n\n"
        f"{login_url}\n\n"
        f"—\n{t['tagline']}\n{t['footer']}"
    )
    return t["subject"], body


def render_welcome_html(*, nickname: str, login_url: str, lang: str = "en") -> str:
    t = pick_locale(_I18N, lang)
    nick = nickname or "there"
    steps = [
        (t["step1_title"], t["step1_desc"]),
        (t["step2_title"], t["step2_desc"]),
        (t["step3_title"], t["step3_desc"]),
    ]
    inner = (
        paragraph(t["greeting"].format(nickname=nick), margin_bottom=12)
        + paragraph(t["intro"])
        + steps_list(steps)
        + cta_button(login_url, t["cta"])
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
