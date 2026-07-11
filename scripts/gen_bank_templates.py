#!/usr/bin/env python3
"""Generate the new BANK_STATEMENT_TEMPLATES section for materialTemplates.js.

Layout: 4 bankKeys (CN/VN/ID/SG) × 4 display locales (zh/en/vi/id).
For every combination we emit a full { title, subtitle, meta, columns,
transactions[28], summary, note } object so the wizard preview shows
amounts + currency + labels in the user's familiar language.

Output:
  /Users/apple/Desktop/签证项目_副本/scripts/gen_bank_templates.py
  writes /Users/apple/Desktop/签证项目_副本/scripts/bank_templates.new.js

Run from anywhere with system Python 3 (no deps).
"""
from __future__ import annotations

from pathlib import Path

OUTPUT = Path("/Users/apple/Desktop/签证项目_副本/scripts/bank_templates.new.js")

# --------------------------------------------------------------------------- #
# Per-bankKey salary anchors, by display locale.
#
# Design rule (W49 v3): keep the *monthly salary* at "young professional,
# 1–3 yrs experience" range. The bank statement's job is to show
# "balance ≥ 6-months-of-savings threshold" (≈ $7K USD = ¥50K / ₫175M /
# Rp115M), not "I earn a lot". All bankKeys (CN/VN/ID/SG) on the SAME
# display locale render the same numbers — only the meta labels and bank
# name differ — so the user always sees their familiar currency at a
# familiar magnitude.
#
# Statement period: 2026-01-01 → 2026-06-30 (6 months ending mid-2026).
# --------------------------------------------------------------------------- #
SALARY = {
    # bankKey   CNY       USD       VND         IDR
    "CN": {"CNY":   7000, "USD":  950, "VND":  23_000_000, "IDR":  15_000_000},
    "VN": {"CNY":   5000, "USD":  680, "VND":  17_000_000, "IDR":  11_000_000},
    "ID": {"CNY":   4000, "USD":  550, "VND":  13_000_000, "IDR":   8_500_000},
    "SG": {"CNY":  18000, "USD": 2500, "VND":  63_000_000, "IDR":  40_500_000},
}

# Each transaction's "share of monthly salary" — independent of bank/locale
# so the structure stays consistent across all 16 combos. Magnitudes chosen
# so the breakdown reads naturally for a young professional applicant.
TXN_RATIO = [
    # (key, type, desc_template, category, credit_ratio_or_None, debit_ratio_or_None)
    # Monthly recurring
    ("SAL",     "credit",  None, None,        1.0,    None),  # salary full
    ("RENT",    "debit",   None, None,        None,   0.40),  # rent ~40% of monthly
    ("UTIL_E",  "debit",   None, None,        None,   0.02),  # electricity
    ("UTIL_W",  "debit",   None, None,        None,   0.015), # water
    ("DINING",  "debit",   None, None,        None,   0.012), # daily dining
    ("RIDE",    "debit",   None, None,        None,   0.020), # ride-hailing
    ("GROCERY", "debit",   None, None,        None,   0.025), # weekly grocery
    ("PHONE",   "debit",   None, None,        None,   0.012), # phone bill
    ("FITNESS", "debit",   None, None,        None,   0.006), # gym
    ("MEDICAL", "debit",   None, None,        None,   0.011), # medical
    ("TRANSFER_IN", "credit", None, None,     0.10,   None),  # transfer in (small)
    ("BONUS",   "credit",  None, None,        1.8,    None),  # bonus
    ("INTEREST","credit",  None, None,        0.001,  None),  # bank interest
]

# Display currency meta for each (bankKey, currency_code)
# Since the display currency follows the user's locale (not the bankKey),
# we only need 4 rows per bankKey showing what the user's CNY/USD/VND/IDR
# equivalent looks like in the meta block.
CURRENCY_META = {
    # bankKey: { ccy: (currency_code, currency_label_for_meta) }
    "CN": {
        "CNY": ("CNY", "人民币 (CNY)"),
        "USD": ("USD", "CNY"),       # W67: 英文 UI 也展示 CNY(纯 ISO 4217 字母,不带中文)
        "VND": ("VND", "VND"),       # vi 用户看 VND,保留本地币
        "IDR": ("IDR", "IDR"),       # id 用户看 IDR,保留本地币
    },
    "VN": {
        "CNY": ("CNY", "人民币 (CNY)"),
        "USD": ("USD", "CNY"),
        "VND": ("VND", "VND"),
        "IDR": ("IDR", "IDR"),
    },
    "ID": {
        "CNY": ("CNY", "人民币 (CNY)"),
        "USD": ("USD", "CNY"),
        "VND": ("VND", "VND"),
        "IDR": ("IDR", "IDR"),
    },
    "SG": {
        "CNY": ("CNY", "人民币 (CNY)"),
        "USD": ("USD", "CNY"),
        "VND": ("VND", "VND"),
        "IDR": ("IDR", "IDR"),
    },
}

# --------------------------------------------------------------------------- #
# Localisation tables
# --------------------------------------------------------------------------- #
TITLES = {
    "zh": "个人账户历史交易明细表",
    "en": "PERSONAL ACCOUNT STATEMENT",
    "vi": "SAO KÊ TÀI KHOẢN CÁ NHÂN",
    "id": "REKENING KORAN PRIBADI",
}
SUBTITLES = {
    "zh": "Personal Account Transaction History Statement",
    "en": "Savings Account — Transaction History",
    "vi": "Personal Account Statement — Transaction History",
    "id": "Personal Account Statement — Transaction History",
}
SUMMARY_LABEL = {
    "zh": "本期合计",
    "en": "6-Month Statement Total",
    "vi": "TỔNG CỘNG 6 THÁNG",
    "id": "TOTAL 6 BULAN",
}
NOTES = {
    "zh": "1. 本证明系个人在自助渠道办理,持卡人保证依据本人银行卡、卡密码、身份证件等个人资料,通过本人账户办理。\n2. 记账日期/时间为系统进行记账处理的日期/时间,可能与实际交易提交时间存在差异。\n3. 本文件仅供签证申请用途,不作其他用途。",
    "en": "1. This is a computer-generated statement. No signature is required.\n2. Please examine this statement carefully. Notify the bank within 30 days if there are any discrepancies.",
    "vi": "1. Sao kê do hệ thống ngân hàng tạo tự động, có giá trị xác nhận giao dịch.\n2. Vui lòng kiểm tra và liên hệ ngân hàng nếu có sai sót trong vòng 30 ngày.",
    "id": "1. Rekening koran ini dicetak otomatis oleh sistem bank dan sah tanpa tanda tangan.\n2. Mohon periksa dengan teliti. Hubungi bank dalam 30 hari jika ada ketidaksesuaian.",
}

# Meta field names per locale (replace the hardcoded zh keys + en keys)
META_FIELDS = {
    "zh": {
        "name": "姓名", "account": "账号", "id_no": "身份证",
        "currency": "币种", "period": "期间", "print_date": "打印日期", "page": "页码",
    },
    "en": {
        "name": "Name", "account": "Account No.", "id_no": "NRIC/Passport",
        "currency": "Currency", "period": "Period", "print_date": "Print Date", "page": "Page",
    },
    "vi": {
        "name": "Tên TK", "account": "Số TK", "id_no": "CCCD",
        "currency": "Loại tiền", "period": "Kỳ", "print_date": "Ngày in", "page": "Trang",
    },
    "id": {
        "name": "Nama", "account": "No. Rek", "id_no": "KTP",
        "currency": "Mata Uang", "period": "Periode", "print_date": "Tgl Cetak", "page": "Halaman",
    },
}

COLUMNS = {
    "zh": ["记账日期", "交易摘要", "交易类目", "收入(元)", "支出(元)", "余额(元)"],
    "en": ["Date", "Description", "Category", "Withdrawal", "Deposit", "Balance"],
    "vi": ["Ngày GD", "Nội dung", "Loại", "Ghi nợ", "Ghi có", "Số dư"],
    "id": ["Tanggal", "Keterangan", "Kategori", "Debet", "Kredit", "Saldo"],
}

# Transaction description + category per (txn_key, locale)
TXN_TEXT = {
    "zh": {
        "SAL":         ("工资入账 — XXX",            "工资收入"),
        "BONUS":       ("奖金入账 — 2025 年度绩效",   "奖金收入"),
        "INTEREST":    ("账户结息",                   "利息收入"),
        "TRANSFER_IN": ("本人其他账户转入",           "转账收入"),
        "RENT":        ("网银支付 — 房租",            "住房"),
        "UTIL_E":      ("网银支付 — 水电费",          "公共事业"),
        "UTIL_W":      ("网银支付 — 燃气费",          "公共事业"),
        "DINING":      ("网银支付 — 餐饮类",          "餐饮"),
        "RIDE":        ("快捷支付 — 出行类(打车)",    "出行"),
        "GROCERY":     ("银联快捷 — 超市购物",        "购物"),
        "PHONE":       ("中国移动",                    "通讯"),
        "FITNESS":     ("网银支付 — 健身房月费",      "健身"),
        "MEDICAL":     ("快捷支付 — 医疗类",          "医疗"),
    },
    "en": {
        "SAL":         ("GIRO Payroll — XXX",                        "Salary"),
        "BONUS":       ("Performance Bonus — 2025 Annual",            "Bonus"),
        "INTEREST":    ("Interest Credit",                             "Interest"),
        "TRANSFER_IN": ("Transfer from own account",                   "Transfer"),
        "RENT":        ("GIRO — Monthly Rent",                          "Housing"),
        "UTIL_E":      ("Card Purchase — Utilities (Electricity)",      "Utilities"),
        "UTIL_W":      ("Card Purchase — Utilities (Water)",           "Utilities"),
        "DINING":      ("Card Purchase — Dining",                      "Dining"),
        "RIDE":        ("Card Purchase — Transport (Ride-hailing)",    "Transport"),
        "GROCERY":     ("Card Purchase — Supermarket",                  "Shopping"),
        "PHONE":       ("Card Purchase — Telecom",                     "Telecom"),
        "FITNESS":     ("Card Purchase — Gym membership",               "Fitness"),
        "MEDICAL":     ("Card Purchase — Medical",                     "Medical"),
    },
    "vi": {
        "SAL":         ("Nhận lương — XXX",                            "Lương"),
        "BONUS":       ("Thưởng Tết Nguyên Đán",                       "Thưởng"),
        "INTEREST":    ("Lãi tiền gửi tiết kiệm",                       "Lãi"),
        "TRANSFER_IN": ("Chuyển từ tài khoản khác của tôi",            "Chuyển khoản"),
        "RENT":        ("Thanh toán — Tiền thuê nhà",                  "Nhà ở"),
        "UTIL_E":      ("Thanh toán — Điện nước",                      "Tiện ích"),
        "UTIL_W":      ("Thanh toán — Nước",                           "Tiện ích"),
        "DINING":      ("Thanh toán QR — Ăn uống",                     "Ăn uống"),
        "RIDE":        ("Thanh toán — Di chuyển",                       "Di chuyển"),
        "GROCERY":     ("Mua sắm — Siêu thị",                          "Mua sắm"),
        "PHONE":       ("Viettel — Cước điện thoại",                   "Viễn thông"),
        "FITNESS":     ("Đăng ký phòng gym tháng",                     "Thể thao"),
        "MEDICAL":     ("Thanh toán — Khám bệnh",                       "Y tế"),
    },
    "id": {
        "SAL":         ("Gaji bulanan — XXX",                          "Gaji"),
        "BONUS":       ("Bonus tahunan 2025",                          "Bonus"),
        "INTEREST":    ("Bunga tabungan",                              "Bunga"),
        "TRANSFER_IN": ("Transfer dari rekening sendiri",              "Transfer"),
        "RENT":        ("Pembayaran — Sewa rumah",                     "Tempat tinggal"),
        "UTIL_E":      ("Pembayaran — Listrik & Air",                  "Utilitas"),
        "UTIL_W":      ("Pembayaran — Air",                            "Utilitas"),
        "DINING":      ("Pembayaran QR — Makan & minum",               "Makan"),
        "RIDE":        ("Transportasi online",                          "Transportasi"),
        "GROCERY":     ("Belanja bulanan — Supermarket",               "Belanja"),
        "PHONE":       ("Telkomsel — Pulsa & paket data",              "Telekomunikasi"),
        "FITNESS":     ("Membership gym bulanan",                       "Fitness"),
        "MEDICAL":     ("Konsultasi dokter",                            "Kesehatan"),
    },
}

# Day-of-month pattern for each (month_idx 0..5, txn_key). 0-indexed month.
# Some entries only appear in some months (BONUS = month 1 / Feb, INTEREST = month 5 / Jun).
TXN_SCHEDULE = [
    # (month_idx, day, key)
    (0, 5, "SAL"),
    (0, 8, "DINING"),
    (0, 15, "RIDE"),
    (0, 20, "GROCERY"),
    (0, 25, "RENT"),
    (0, 28, "PHONE"),
    (1, 5, "SAL"),
    (1, 9, "BONUS"),       # CN bonus
    (1, 14, "DINING"),
    (1, 20, "RIDE"),
    (1, 22, "TRANSFER_IN"),
    (1, 25, "RENT"),
    (1, 28, "UTIL_E"),
    (2, 5, "SAL"),
    (2, 12, "RIDE"),       # air ticket - large
    (2, 15, "GROCERY"),
    (2, 18, "UTIL_E"),
    (2, 25, "RENT"),
    (3, 5, "SAL"),
    (3, 8, "DINING"),
    (3, 15, "MEDICAL"),
    (3, 22, "FITNESS"),
    (3, 25, "RENT"),
    (4, 5, "SAL"),
    (4, 10, "DINING"),
    (4, 18, "GROCERY"),
    (4, 25, "RENT"),
    (4, 28, "UTIL_W"),
    (5, 5, "SAL"),
    (5, 12, "DINING"),
    (5, 21, "INTEREST"),
    (5, 25, "RENT"),
]

# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #

def fmt_amount(n: float, locale: str) -> str:
    """Format a transaction amount in the user's locale style.
    - en/zh: comma thousands, 2 decimals → 1,234.56
    - vi/id: dot thousands, 2 decimals → 1.234,56
    """
    if locale in ("zh", "en"):
        # English-style: 1,234.56
        s = f"{abs(n):,.2f}"
        return s
    else:  # vi / id: 1.234,56
        s = f"{abs(n):,.2f}"  # → 1,234.56
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
        return s


def fmt_date(day: int, month_idx: int, locale: str) -> str:
    """Per-locale date format. W49 v3: refreshed to 2026 statement period."""
    year = 2026
    if locale == "zh":
        return f"{year}/{month_idx + 1:02d}/{day:02d}"
    if locale == "en":
        # '05 Jan 2026'
        import calendar
        month_abbr = calendar.month_abbr[month_idx + 1]
        return f"{day:02d} {month_abbr} {year}"
    if locale == "vi":
        return f"{day:02d}/{month_idx + 1:02d}/{year}"
    if locale == "id":
        return f"{day:02d}/{month_idx + 1:02d}/{year}"
    return f"{year}/{month_idx + 1:02d}/{day:02d}"


def fmt_period(locale: str) -> str:
    if locale == "zh":
        return "2026/01/01 — 2026/06/30"
    if locale == "en":
        return "01 Jan 2026 — 30 Jun 2026"
    if locale == "vi":
        return "01/01/2026 — 30/06/2026"
    if locale == "id":
        return "01 Januari — 30 Juni 2026"
    return ""


def fmt_print_date(locale: str) -> str:
    if locale == "zh":
        return "2026/07/05 11:23:08"
    if locale == "en":
        return "05 Jul 2026, 09:45 SGT"
    if locale == "vi":
        return "05/07/2026 09:15"
    if locale == "id":
        return "05/07/2026 10:23 WIB"
    return ""


# --------------------------------------------------------------------------- #
# Build one template per (bankKey, locale)
# --------------------------------------------------------------------------- #

def build_template(bank_key: str, locale: str) -> dict:
    LOCALE_TO_CCY = {"zh": "CNY", "en": "USD", "vi": "VND", "id": "IDR"}
    ccy = LOCALE_TO_CCY[locale]
    salary = SALARY[bank_key][ccy]
    cur_code, cur_label = CURRENCY_META[bank_key][ccy]
    meta_fields = META_FIELDS[locale]
    cols = COLUMNS[locale]
    title = TITLES[locale]
    subtitle = SUBTITLES[locale]
    summary_label = SUMMARY_LABEL[locale]
    note = NOTES[locale]

    # Build transactions
    transactions = []
    running_balance = 0.0
    total_credit = 0.0
    total_debit = 0.0
    for (month_idx, day, key) in TXN_SCHEDULE:
        text_table = TXN_TEXT[locale]
        desc, category = text_table[key]
        ratio = next(r for r in TXN_RATIO if r[0] == key)
        is_credit = ratio[1] == "credit"
        amount_ratio = ratio[4 if is_credit else 5]
        amount = salary * amount_ratio
        running_balance += amount if is_credit else -amount
        if is_credit:
            total_credit += amount
        else:
            total_debit += amount
        transactions.append({
            "month": month_idx + 1,
            "date": fmt_date(day, month_idx, locale),
            "desc": desc,
            "category": category,
            "isCredit": is_credit,
            "credit": fmt_amount(amount, locale) if is_credit else "",
            "debit":  fmt_amount(amount, locale) if not is_credit else "",
            "balance": fmt_amount(running_balance, locale),
        })

    # Meta
    meta = {
        meta_fields["name"]: "XXX",
        meta_fields["account"]: "XXX",
        meta_fields["id_no"]: "XXX",
        meta_fields["currency"]: cur_label,
        meta_fields["period"]: fmt_period(locale),
        meta_fields["print_date"]: fmt_print_date(locale),
        meta_fields["page"]: "1 / 2" if locale in ("zh", "vi", "id") else "1 of 2",
    }

    # Summary
    sign = "+" if locale in ("en",) else ("+" if True else "")
    summary = {
        "label": summary_label,
        "credit": f"+{fmt_amount(total_credit, locale)}",
        "debit":  f"-{fmt_amount(total_debit, locale)}",
        "balance": fmt_amount(running_balance, locale),
    }

    return {
        "title": title,
        "subtitle": subtitle,
        "meta": meta,
        "columns": cols,
        "transactions": transactions,
        "summary": summary,
        "note": note,
    }


# --------------------------------------------------------------------------- #
# Emit the JS module
# --------------------------------------------------------------------------- #

def js_str(s: str) -> str:
    """JS-safe single-quoted string."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def main() -> None:
    lines: list[str] = []
    lines.append("// Auto-generated by scripts/gen_bank_templates.py — do not hand-edit.")
    lines.append("// Layout: 4 bankKeys (CN/VN/ID/SG) × 4 display locales (zh/en/vi/id).")
    lines.append("// Amounts + currency + labels all follow the user's locale — vi users")
    lines.append("// see ₫ magnitudes regardless of which visa destination they're viewing.")
    lines.append("// Generated at " + "run-time" + " — to re-emit: python3 scripts/gen_bank_templates.py")
    lines.append("export const BANK_STATEMENT_TEMPLATES = {")
    for bank_key in ("CN", "VN", "ID", "SG"):
        lines.append(f"  {bank_key}: {{")
        lines.append(f"    bankStatement: {{")
        for locale in ("zh", "en", "vi", "id"):
            tpl = build_template(bank_key, locale)
            lines.append(f"      {locale}: {{")
            lines.append(f"        title: {js_str(tpl['title'])},")
            lines.append(f"        subtitle: {js_str(tpl['subtitle'])},")
            meta_kv = ", ".join(f"{js_str(k)}: {js_str(v)}" for k, v in tpl["meta"].items())
            lines.append(f"        meta: {{ {meta_kv} }},")
            cols_str = ", ".join(js_str(c) for c in tpl["columns"])
            lines.append(f"        columns: [{cols_str}],")
            lines.append(f"        transactions: [")
            for tx in tpl["transactions"]:
                kv = (
                    f"month: {tx['month']}, date: {js_str(tx['date'])}, "
                    f"desc: {js_str(tx['desc'])}, category: {js_str(tx['category'])}, "
                    f"isCredit: {str(tx['isCredit']).lower()}, "
                    f"credit: {js_str(tx['credit'])}, debit: {js_str(tx['debit'])}, "
                    f"balance: {js_str(tx['balance'])}"
                )
                lines.append(f"          {{ {kv} }},")
            lines.append(f"        ],")
            sk = tpl["summary"]
            lines.append(
                f"        summary: {{ label: {js_str(sk['label'])}, "
                f"credit: {js_str(sk['credit'])}, debit: {js_str(sk['debit'])}, "
                f"balance: {js_str(sk['balance'])} }},"
            )
            lines.append(f"        note: {js_str(tpl['note'])},")
            lines.append(f"      }},")
        lines.append(f"    }},")
        lines.append(f"  }},")
    lines.append("}")
    lines.append("")

    OUTPUT.write_text("\n".join(lines))
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()