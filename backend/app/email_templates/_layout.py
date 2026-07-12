"""Shared HTML email layout — table-based, inline styles, 600px card."""
from __future__ import annotations

from html import escape


def pick_locale(strings: dict[str, dict[str, str]], lang: str) -> dict[str, str]:
    return strings.get(lang) or strings.get((lang or "").split("-")[0]) or strings["en"]


def email_shell(
    *,
    lang: str,
    subject: str,
    preheader: str,
    title: str,
    body_html: str,
    tagline: str,
    footer: str,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="{escape(lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(subject)}</title>
</head>
<body style="margin:0;padding:0;background-color:#F8FAFC;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Helvetica Neue',Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F8FAFC;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;box-shadow:0 1px 3px rgba(15,23,42,0.06);">
        <tr><td style="padding:40px 32px;">
          <div style="font-size:24px;font-weight:900;color:#000000;letter-spacing:-0.5px;margin-bottom:32px;">Htex</div>
          <h1 style="margin:0 0 12px;font-size:22px;line-height:1.3;font-weight:700;color:#0F172A;">{escape(title)}</h1>
          {body_html}
        </td></tr>
      </table>
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;margin-top:24px;">
        <tr><td align="center" style="font-size:12px;line-height:18px;color:#94A3B8;">
          <div style="margin-bottom:4px;">{escape(tagline)}</div>
          <div>{escape(footer)}</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def paragraph(text: str, *, margin_bottom: int = 28) -> str:
    return (
        f'<p style="margin:0 0 {margin_bottom}px;font-size:15px;line-height:24px;'
        f'color:#334155;max-width:480px;">{escape(text)}</p>'
    )


def muted(text: str, *, margin_bottom: int = 28) -> str:
    return (
        f'<p style="margin:0 0 {margin_bottom}px;font-size:13px;line-height:20px;'
        f'color:#64748B;">{escape(text)}</p>'
    )


def divider() -> str:
    return '<hr style="border:none;border-top:1px solid #E2E8F0;margin:28px 0;">'


def code_block(code: str) -> str:
    spaced = " ".join(code)
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
      <tr><td style="background-color:#F1F5F9;border-left:4px solid #3B6EF5;border-radius:10px;padding:20px 32px;text-align:center;">
        <div style="font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:36px;font-weight:700;letter-spacing:8px;color:#0F172A;">{escape(spaced)}</div>
      </td></tr>
    </table>"""


def cta_button(url: str, label: str) -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
      <tr><td style="border-radius:10px;background-color:#3B6EF5;">
        <a href="{escape(url)}" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;color:#FFFFFF;text-decoration:none;border-radius:10px;">{escape(label)}</a>
      </td></tr>
    </table>"""


def link_fallback(url: str) -> str:
    return (
        f'<p style="margin:0 0 28px;font-size:12px;line-height:18px;color:#94A3B8;word-break:break-all;">'
        f'{escape(url)}</p>'
    )


def steps_list(items: list[tuple[str, str]]) -> str:
    rows = []
    for i, (title, desc) in enumerate(items, 1):
        rows.append(
            f'<tr><td style="padding:0 0 14px;font-size:14px;line-height:22px;color:#334155;">'
            f'<strong style="color:#0F172A;">{i}. {escape(title)}</strong> — {escape(desc)}'
            f'</td></tr>'
        )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">'
        + "".join(rows)
        + "</table>"
    )


def success_banner(text: str) -> str:
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
      <tr><td style="background-color:#F0FDF4;border-left:4px solid #16A34A;border-radius:10px;padding:16px 20px;">
        <div style="font-size:14px;line-height:22px;color:#166534;font-weight:600;">{escape(text)}</div>
      </td></tr>
    </table>"""
