"""Generate test fixtures for the 3 new features.

Creates:
  - 06_id_card_cn.png  : Chinese ID card (正面, 居民身份证)
  - 07_photo_white.png : White-background 2-inch visa photo
  - 08_ds160_form.png  : DS-160 confirmation page mockup
  - 09_bank_statement.pdf: bank statement PDF (text-only)
"""
import io
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "outputs" / "test-fixtures"
OUT.mkdir(parents=True, exist_ok=True)


# Pick a CJK-capable font (system fallback)
def get_cjk_font(size: int = 16):
    for path in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Songti.ttc",
    ]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_id_card():
    """CN ID card front (居民身份证)."""
    W, H = 856, 540  # standard CN ID aspect (85.6mm × 54mm)
    img = Image.new("RGB", (W, H), (255, 245, 220))  # light beige background
    d = ImageDraw.Draw(img)
    f_title = get_cjk_font(28)
    f_lg = get_cjk_font(20)
    f_sm = get_cjk_font(14)

    # Title
    d.text((30, 20), "中华人民共和国居民身份证", fill=(180, 30, 30), font=f_title)
    d.rectangle([(20, 18), (W - 20, H - 18)], outline=(180, 30, 30), width=3)

    # Photo placeholder (right side)
    d.rectangle([(W - 220, 80), (W - 50, 250)], outline=(80, 80, 80), width=2)
    d.text((W - 175, 155), "证件照", fill=(120, 120, 120), font=f_lg)

    # Fields (left side)
    fields = [
        ("姓名", "张 三"),
        ("性别", "男"),
        ("民族", "汉"),
        ("出生", "1990 年 01 月 15 日"),
        ("住址", "北京市朝阳区某某街道某某号"),
        ("公民身份号码", "110101199001151234"),
    ]
    y = 90
    for label, value in fields:
        d.text((50, y), label, fill=(60, 60, 60), font=f_lg)
        d.text((150, y), value, fill=(0, 0, 0), font=f_lg)
        y += 40

    # Issuer
    d.text((50, H - 60), "签发机关: 北京市公安局朝阳分局", fill=(60, 60, 60), font=f_sm)
    d.text((50, H - 35), "有效期: 2015.01.15 - 2035.01.15", fill=(60, 60, 60), font=f_sm)

    img.save(OUT / "06_id_card_cn.png", "PNG")
    print(f"✓ {OUT / '06_id_card_cn.png'}")


def make_visa_photo():
    """White-bg 2-inch visa photo."""
    W, H = 480, 600  # ~ 33mm × 41mm at 350dpi (close to 2 inch)
    img = Image.new("RGB", (W, H), (255, 255, 255))  # pure white bg
    d = ImageDraw.Draw(img)

    # head silhouette (gray ellipse on white)
    cx, cy = W // 2, H // 2
    head_w, head_h = int(W * 0.42), int(H * 0.42)
    d.ellipse(
        [cx - head_w // 2, cy - head_h // 2 - 30, cx + head_w // 2, cy + head_h // 2 - 30],
        fill=(200, 200, 210),
    )
    # shoulders (trapezoid)
    d.polygon(
        [
            (cx - int(W * 0.35), H - 40),
            (cx + int(W * 0.35), H - 40),
            (cx + int(W * 0.30), H - 180),
            (cx - int(W * 0.30), H - 180),
        ],
        fill=(180, 180, 195),
    )

    img.save(OUT / "07_photo_white.png", "PNG")
    print(f"✓ {OUT / '07_photo_white.png'}")


def make_ds160():
    """DS-160 confirmation page mockup."""
    W, H = 1200, 1600  # A4-ish portrait
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    f_title = get_cjk_font(36)
    f_h = get_cjk_font(22)
    f_b = get_cjk_font(18)

    # Header banner
    d.rectangle([(0, 0), (W, 110)], fill=(0, 51, 102))
    d.text((30, 30), "DS-160 Confirmation", fill=(255, 255, 255), font=f_title)
    d.text((30, 75), "Nonimmigrant Visa Application", fill=(200, 220, 255), font=f_h)

    y = 160
    d.text((50, y), "Application ID: AA12345678", fill=(0, 0, 0), font=f_h)
    y += 50

    sections = [
        ("Personal Information", [
            "Surname: ZHANG", "Given Name: SAN",
            "Full Name in Native Language: 张三",
            "Sex: Male", "Marital Status: Single",
            "Date of Birth: 1990-01-15", "Place of Birth: BEIJING, CHINA",
        ]),
        ("Passport Information", [
            "Passport Number: G12345678",
            "Country/Region of Issuance: CHINA",
            "Date of Issue: 2020-03-12",
            "Date of Expiry: 2030-03-11",
        ]),
        ("Travel Information", [
            "Purpose of Trip: B1/B2 (Business/Tourism)",
            "Specific Travel Plans: Tourism",
            "Intended Date of Arrival: 2026-12-01",
            "Intended Length of Stay: 14 days",
        ]),
        ("US Contact Information", [
            "Contact Person: John Smith",
            "Organization: ABC Hotel",
            "Address: 123 Main St, New York, NY 10001",
            "Phone: 1-212-555-1234",
        ]),
    ]
    for title, lines in sections:
        d.rectangle([(50, y), (W - 50, y + 35)], fill=(220, 230, 245))
        d.text((60, y + 5), title, fill=(0, 51, 102), font=f_h)
        y += 45
        for line in lines:
            d.text((80, y), "• " + line, fill=(40, 40, 40), font=f_b)
            y += 30
        y += 15

    # Footer bar
    d.rectangle([(0, H - 60), (W, H)], fill=(0, 51, 102))
    d.text((30, H - 45), "DS-160 Confirmation Page — Print and bring to interview",
           fill=(255, 255, 255), font=f_b)
    img.save(OUT / "08_ds160_form.png", "PNG")
    print(f"✓ {OUT / '08_ds160_form.png'}")


def make_bank_statement_pdf():
    """Bank statement as a multi-page text PDF (no real bank logo)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        print("reportlab not installed, skipping bank statement PDF")
        return

    c = canvas.Canvas(str(OUT / "09_bank_statement.pdf"), pagesize=A4)
    W, H = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, H - 80, "BANK STATEMENT")
    c.setFont("Helvetica", 12)
    c.drawString(50, H - 110, "Account Holder: ZHANG SAN")
    c.drawString(50, H - 130, "Account Number: ****1234")
    c.drawString(50, H - 150, "Statement Period: 2026-01-01 to 2026-03-31")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, H - 200, "Transaction History")
    c.setFont("Helvetica", 11)
    headers = ["Date", "Description", "Amount (CNY)", "Balance"]
    x = [60, 200, 400, 500]
    y = H - 230
    for h, x_pos in zip(headers, x):
        c.drawString(x_pos, y, h)
    y -= 20
    rows = [
        ("2026-01-05", "Salary deposit",        "+18,500.00",  "52,300.00"),
        ("2026-01-12", "Utility bill payment",  "-  320.00",  "51,980.00"),
        ("2026-01-25", "Grocery - Walmart",     "-  450.00",  "51,530.00"),
        ("2026-02-01", "Rent payment",          "- 4,500.00", "47,030.00"),
        ("2026-02-14", "Restaurant",            "-  180.00",  "46,850.00"),
        ("2026-02-28", "Salary deposit",        "+18,500.00",  "65,350.00"),
        ("2026-03-05", "Online shopping",       "-  680.00",  "64,670.00"),
        ("2026-03-15", "Insurance premium",     "-1,200.00",  "63,470.00"),
        ("2026-03-25", "Taxi & transit",        "-  220.00",  "63,250.00"),
        ("2026-03-30", "Savings transfer",      "-5,000.00",  "58,250.00"),
    ]
    for row in rows:
        for cell, x_pos in zip(row, x):
            c.drawString(x_pos, y, cell)
        y -= 18
    c.save()
    print(f"✓ {OUT / '09_bank_statement.pdf'}")


if __name__ == "__main__":
    make_id_card()
    make_visa_photo()
    make_ds160()
    make_bank_statement_pdf()
    print("\nAll test fixtures generated.")
    print(f"Output dir: {OUT}")