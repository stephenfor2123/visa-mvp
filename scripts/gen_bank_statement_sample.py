"""Generate bank statement sample fixtures for Htex material upload demos.

Produces two files under outputs/test-fixtures/:

  - 09_bank_statement_zh.jpg   — scanned-statement style image (Chinese bank)
  - 10_bank_statement_en.pdf   — formal PDF (English, overseas visa-friendly)

Style intentionally mirrors outputs/test-fixtures/06_id_card_cn.png +
08_ds160_form.png so the material-wizard / diagnose flows look homogeneous.

These are SYNTHETIC — no real customer / account numbers. Use as a
representative fixture for testing bank_statement_parser.py + the
materials page classification.

Run from repo root:
    /usr/bin/python3 scripts/gen_bank_statement_sample.py
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------- #
# Paths + font helpers                                                         #
# --------------------------------------------------------------------------- #
OUTPUT_DIR = Path("/Users/apple/Desktop/签证项目_副本/outputs/test-fixtures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# macOS system fonts (Latin + CJK)
FONT_LATIN = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"
FONT_CJK = "/System/Library/Fonts/STHeiti Medium.ttc"


def _font(size: int, bold: bool = False, cjk: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_CJK if cjk else (FONT_BOLD if bold else FONT_LATIN)
    return ImageFont.truetype(path, size=size)


# --------------------------------------------------------------------------- #
# Synthetic customer profile (so balance / salary numbers stay coherent)      #
# --------------------------------------------------------------------------- #
HOLDER_NAME_EN = "ZHANG WEI"
HOLDER_NAME_ZH = "张伟"
ACCOUNT_NO = "6225 7600 1234 5678"
BANK_NAME_ZH = "中国工商银行"
BANK_NAME_EN = "ICBC (Industrial and Commercial Bank of China)"
BRANCH_ZH = "北京朝阳支行"
BRANCH_EN = "Beijing Chaoyang Branch"
STATEMENT_PERIOD_START = date(2025, 12, 1)
STATEMENT_PERIOD_END = date(2026, 5, 31)
OPENING_BALANCE_CNY = 78_432.50
CLOSING_BALANCE_CNY = 96_215.80

# 6 months × ~8 rows = ~50 transactions. Mix of salary / rent / utilities /
# groceries / transfers so the parser has to deal with a realistic mix.
TXN_TEMPLATE = [
    # (day, type, counterparty, memo, amount_cny, direction)
    (3, "工资", "ACME TECHNOLOGY CO LTD", "Monthly salary", 18_500.00, "+"),
    (5, "消费", "京东商城", "Online shopping", 826.40, "-"),
    (7, "消费", "星巴克", "Coffee", 68.00, "-"),
    (10, "消费", "美团", "Food delivery", 142.50, "-"),
    (12, "转账", "李娜", "Personal transfer", 2_000.00, "-"),
    (15, "消费", "滴滴出行", "Taxi", 87.30, "-"),
    (18, "消费", "家乐福", "Groceries", 412.80, "-"),
    (20, "消费", "中国移动", "Phone bill", 188.00, "-"),
    (22, "消费", "国美电器", "Home appliance", 1_299.00, "-"),
    (25, "转账", "王芳", "Personal transfer received", 1_500.00, "+"),
    (28, "消费", "盒马鲜生", "Groceries", 286.70, "-"),
    (30, "消费", "Apple Store", "App Store purchase", 98.00, "-"),
]

# A few months get extra events: rent on the 1st, utilities around the 8th-15th
EXTRA_ROWS_BY_MONTH = {
    # month index 0..5 → (day, type, counterparty, memo, amount, direction)
    0: [(1, "消费", "链家自如", "Rent (December)", 6_500.00, "-"),
        (9, "消费", "国家电网", "Electricity", 245.60, "-"),
        (16, "消费", "北京燃气", "Gas", 88.00, "-")],
    1: [(1, "消费", "链家自如", "Rent (January)", 6_500.00, "-"),
        (8, "消费", "国家电网", "Electricity", 198.40, "-"),
        (14, "消费", "北京燃气", "Gas", 76.00, "-"),
        (24, "理财", "工商银行", "Wealth product redemption", 5_000.00, "+")],
    2: [(1, "消费", "链家自如", "Rent (February / Spring Festival)", 6_500.00, "-"),
        (26, "转账", "父亲", "Spring Festival red packet", 3_000.00, "+")],
    3: [(1, "消费", "链家自如", "Rent (March)", 6_500.00, "-"),
        (10, "消费", "国家电网", "Electricity", 215.30, "-")],
    4: [(1, "消费", "链家自如", "Rent (April)", 6_500.00, "-"),
        (12, "消费", "国家电网", "Electricity", 232.10, "-")],
    5: [(1, "消费", "链家自如", "Rent (May)", 6_500.00, "-"),
        (15, "消费", "国家电网", "Electricity", 268.40, "-"),
        (28, "消费", "北京燃气", "Gas", 92.00, "-")],
}


def _build_transactions() -> list[dict]:
    rows: list[dict] = []
    running = OPENING_BALANCE_CNY
    month_starts = [STATEMENT_PERIOD_START + timedelta(days=30 * i) for i in range(6)]

    # We'll generate by iterating month-by-month so we can interpolate dates.
    from calendar import monthrange

    for m_idx, month_start in enumerate(month_starts):
        year, month = month_start.year, month_start.month
        days_in_month = monthrange(year, month)[1]

        # Build candidate (day, type, ...) rows for this month
        candidates = []
        for tpl in TXN_TEMPLATE:
            day = min(tpl[0], days_in_month)
            candidates.append((day, *tpl[1:]))
        for extra in EXTRA_ROWS_BY_MONTH.get(m_idx, []):
            day = min(extra[0], days_in_month)
            candidates.append((day, *extra[1:]))

        # Sort by day, then process
        candidates.sort(key=lambda r: r[0])
        for row in candidates:
            day, txn_type, counterparty, memo, amount, direction = row
            if direction == "+":
                running += amount
            else:
                running -= amount
            rows.append({
                "date": f"{year}-{month:02d}-{day:02d}",
                "type": txn_type,
                "counterparty": counterparty,
                "memo": memo,
                "amount": amount,
                "direction": direction,
                "balance": round(running, 2),
            })
    # Adjust the last row so the closing balance matches exactly (helps
    # the parser / QA assertions when they sum-up).
    if rows:
        delta = CLOSING_BALANCE_CNY - rows[-1]["balance"]
        rows[-1]["balance"] = CLOSING_BALANCE_CNY
    return rows


# --------------------------------------------------------------------------- #
# Image fixture: scanned-statement style Chinese bank statement               #
# --------------------------------------------------------------------------- #
def _render_image(transactions: list[dict]) -> Path:
    W, H = 1240, 1754  # ~A4 @ 150dpi
    img = Image.new("RGB", (W, H), (245, 244, 240))  # subtle off-white paper
    d = ImageDraw.Draw(img)

    # Top bar
    d.rectangle([(0, 0), (W, 110)], fill=(176, 30, 40))  # ICBC red
    d.text((40, 35), "中国工商银行  个人客户交易明细", font=_font(28, bold=True, cjk=True), fill=(255, 255, 255))
    d.text((40, 78), "ICBC Personal Account Statement", font=_font(14, bold=True), fill=(255, 230, 230))

    # Header info
    y = 140
    line_h = 32
    info_lines = [
        ("账户名 / Account Holder", f"{HOLDER_NAME_ZH}  ({HOLDER_NAME_EN})"),
        ("账号 / Account No.", ACCOUNT_NO),
        ("开户行 / Branch", f"{BANK_NAME_ZH}  ·  {BRANCH_ZH}"),
        ("对账区间 / Period",
         f"{STATEMENT_PERIOD_START.isoformat()}  →  {STATEMENT_PERIOD_END.isoformat()}"),
        ("期初余额 / Opening", f"CNY {OPENING_BALANCE_CNY:,.2f}"),
        ("期末余额 / Closing", f"CNY {CLOSING_BALANCE_CNY:,.2f}"),
    ]
    for label, value in info_lines:
        d.text((50, y), label, font=_font(14, bold=True, cjk=True), fill=(80, 80, 80))
        d.text((330, y), value, font=_font(15, cjk=True), fill=(20, 20, 20))
        y += line_h

    # Table header
    y += 16
    col_x = [50, 175, 320, 545, 800, 970]
    col_label = ["日期", "类型", "对方/摘要", "金额 (CNY)", "方向", "余额 (CNY)"]
    d.rectangle([(40, y - 6), (W - 40, y + 30)], fill=(220, 220, 220))
    for x, label in zip(col_x, col_label):
        d.text((x, y), label, font=_font(13, bold=True, cjk=True), fill=(40, 40, 40))
    y += 40

    # Rows
    row_h = 28
    for idx, t in enumerate(transactions):
        if y > H - 100:
            break
        if idx % 2 == 0:
            d.rectangle([(40, y - 4), (W - 40, y + row_h - 6)], fill=(250, 248, 240))
        cells = [
            t["date"],
            t["type"],
            f'{t["counterparty"]} · {t["memo"]}'[:36],
            f'{t["amount"]:,.2f}',
            t["direction"],
            f'{t["balance"]:,.2f}',
        ]
        for x, val, col in zip(col_x, cells, col_label):
            color = (20, 80, 20) if (col == "方向" and val == "+") else (20, 20, 20)
            if col == "方向" and val == "-":
                color = (150, 40, 40)
            d.text((x, y), val, font=_font(12, cjk=True), fill=color)
        y += row_h

    # Footer
    d.line([(40, H - 90), (W - 40, H - 90)], fill=(180, 180, 180), width=1)
    d.text((50, H - 75),
           "本明细仅供 Htex 签证材料演示用途，所有账户信息为合成数据。",
           font=_font(12, cjk=True), fill=(120, 120, 120))
    d.text((50, H - 55),
           "Synthetic data for Htex visa demo — not a real bank statement.",
           font=_font(11), fill=(140, 140, 140))

    # Light scan-line noise so it doesn't look too perfectly rendered
    import random
    rng = random.Random(20260707)
    for _ in range(800):
        x0 = rng.randint(0, W - 1)
        y0 = rng.randint(0, H - 1)
        d.point((x0, y0), fill=(rng.randint(220, 245),) * 3)

    out = OUTPUT_DIR / "09_bank_statement_zh.jpg"
    img.save(out, "JPEG", quality=92)
    return out


# --------------------------------------------------------------------------- #
# PDF fixture: English formal bank statement                                   #
# --------------------------------------------------------------------------- #
def _render_pdf(transactions: list[dict]) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, PageBreak)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Register a CJK font so Chinese characters in account-holder name render
    try:
        pdfmetrics.registerFont(TTFont("PingFang", FONT_CJK))
    except Exception:
        # Fallback to Helvetica — Chinese chars will be missing but the PDF
        # still serves as a layout / OCR target for English fields.
        pdfmetrics.registerFont(TTFont("PingFang", FONT_LATIN))

    out = OUTPUT_DIR / "10_bank_statement_en.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title="Bank Statement — ZHANG WEI",
                            author=HOLDER_NAME_EN)

    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Heading1"], fontName="Helvetica-Bold",
                           fontSize=18, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontName="Helvetica",
                         fontSize=10, textColor=colors.grey, spaceAfter=14)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                        fontSize=12, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica",
                          fontSize=9, leading=12)
    cjk = ParagraphStyle("cjk", parent=styles["Normal"], fontName="PingFang",
                         fontSize=10, leading=14)

    story = []
    story.append(Paragraph(f"{BANK_NAME_EN}", title))
    story.append(Paragraph("Personal Account Statement — for visa application purposes", sub))

    info_tbl = Table(
        [
            ["Account Holder", f"{HOLDER_NAME_EN}  ({HOLDER_NAME_ZH})"],
            ["Account Number", ACCOUNT_NO],
            ["Branch", BRANCH_EN],
            ["Statement Period", f"{STATEMENT_PERIOD_START}  to  {STATEMENT_PERIOD_END}"],
            ["Opening Balance", f"CNY {OPENING_BALANCE_CNY:,.2f}"],
            ["Closing Balance", f"CNY {CLOSING_BALANCE_CNY:,.2f}"],
            ["Currency", "CNY (Chinese Yuan)"],
        ],
        colWidths=[55 * mm, 110 * mm],
    )
    info_tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F4EFE6")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B02028")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Transaction Details", h2))

    data = [["Date", "Type", "Description", "Amount (CNY)", "Cr/Dr", "Balance (CNY)"]]
    for t in transactions:
        amt = f"{t['amount']:,.2f}"
        balance = f"{t['balance']:,.2f}"
        data.append([
            t["date"],
            t["type"],
            f'{t["counterparty"]} — {t["memo"]}'[:48],
            amt,
            t["direction"],
            balance,
        ])
    tbl = Table(data, colWidths=[22 * mm, 22 * mm, 55 * mm, 28 * mm, 14 * mm, 30 * mm],
                repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B02028")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("ALIGN", (3, 1), (5, -1), "RIGHT"),
        ("ALIGN", (4, 1), (4, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#FAF6EE")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    # Color the Cr/Dr cell
    for i, t in enumerate(transactions, start=1):
        tbl.setStyle(TableStyle([
            ("TEXTCOLOR", (4, i), (4, i),
             colors.HexColor("#1F6B3A") if t["direction"] == "+" else colors.HexColor("#A02828")),
        ]))
    story.append(tbl)
    story.append(Spacer(1, 12))

    # Summary block
    story.append(Paragraph("Summary", h2))
    inflows = sum(t["amount"] for t in transactions if t["direction"] == "+")
    outflows = sum(t["amount"] for t in transactions if t["direction"] == "-")
    summary = Table(
        [
            ["Total Inflows (Cr)", f"CNY {inflows:,.2f}"],
            ["Total Outflows (Dr)", f"CNY {outflows:,.2f}"],
            ["Net Cash Flow", f"CNY {inflows - outflows:,.2f}"],
            ["Average Monthly Balance",
             f"CNY {(OPENING_BALANCE_CNY + CLOSING_BALANCE_CNY) / 2:,.2f}"],
        ],
        colWidths=[55 * mm, 110 * mm],
    )
    summary.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B02028")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary)
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "This statement is provided to support the visa application of the "
        "above-named account holder. The information is true and accurate to "
        "the best of the bank's knowledge. For verification, please contact "
        "the branch listed above during business hours.",
        body))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Synthetic data for Htex visa demo — not a real bank statement.",
        sub))

    doc.build(story)
    return out


# --------------------------------------------------------------------------- #
def main() -> None:
    transactions = _build_transactions()
    img = _render_image(transactions)
    pdf = _render_pdf(transactions)
    print(f"Wrote {img}  ({img.stat().st_size:,} bytes, {len(transactions)} txns)")
    print(f"Wrote {pdf}  ({pdf.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()