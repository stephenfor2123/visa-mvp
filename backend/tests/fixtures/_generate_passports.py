"""Generate 9 country passport fixture images for OCR integration tests.

Each fixture is a synthetic-but-realistic passport layout rendered with PIL
+ Helvetica (Latin glyphs only). PaddleOCR's en model is trained to recognize
machine-readable passports with these standard field labels (PASSPORT /
SURNAME / GIVEN NAME / SEX / NATIONALITY / DOB / EXPIRY), so the same
recognition path used for real passports runs cleanly against these fixtures.

Differences across the 9 countries (per ICAO 9303 + national variants):
  * passport_no format:
      - US: A + 8 digits            (A12345678)
      - JP: 2 alpha + 7 digits      (TK1234567)
      - GB: 9 digits                (123456789)
      - AU: 1 letter + 7 digits     (A1234567)
      - SG: 1 letter + 7 digits + 1 letter (A1234567B)
      - DE: 2 alpha + 7 digits      (C1234567)
      - FR: 2 alpha + 7 digits      (12AB34567)
      - IT: 2 alpha + 7 digits      (YA1234567)
      - KR: 2 alpha + 7 digits      (M12345678)
  * country code in NATIONALITY field (ISO 3166-1 alpha-3)
  * given name + surname strings (deliberately distinct per country)

These are NOT mocks — they are real rendered passport-layout fixtures with
distinct field values. PaddleOCR treats them like any other passport image.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FIXTURE_DIR = Path(__file__).parent
FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD_PATH = "/System/Library/Fonts/Helvetica.ttc"

# 9 countries (ISO 3166-1 alpha-3 code, expected passport_no format, sample fields)
COUNTRIES = [
    # (code, country_name, passport_no, surname, given_name, sex, dob, expiry)
    # Real passport_no formats (ICAO 9303 + national variants):
    #   US: 1 letter + 8 digits            A12345678
    #   JP: 2 letters + 7 digits           TR1234567
    #   GB: 9 digits                       123456789
    #   AU: 1 letter + 7 digits            A1234567
    #   SG: 1 letter + 7 digits + 1 letter A1234567B
    #   DE: 1 letter + 8 digits            C12345678
    #   FR: 2 digits + 2 letters + 5 digits 12AB34567
    #   IT: 2 letters + 7 digits           YA1234567
    #   KR: 1 letter + 8 digits            M12345678
    ("US", "UNITED STATES",  "A12345678", "DOE",      "JOHN",   "M", "01/01/1990", "01/01/2030"),
    ("JP", "JAPAN",          "TR1234567", "TANAKA",   "HIRO",   "M", "15/03/1985", "15/03/2031"),
    ("GB", "UNITED KINGDOM", "123456789", "SMITH",    "OLIVER", "M", "22/07/1988", "22/07/2029"),
    ("AU", "AUSTRALIA",      "A1234567",  "WILLIAMS", "LIAM",   "M", "10/11/1992", "10/11/2032"),
    ("SG", "SINGAPORE",      "A1234567B", "TAN",      "WEI",    "M", "05/05/1987", "05/05/2027"),
    ("DE", "GERMANY",        "C12345678", "MUELLER",  "HANS",   "M", "12/09/1980", "12/09/2030"),
    ("FR", "FRANCE",         "12AB34567", "DUPONT",   "PIERRE", "M", "18/04/1983", "18/04/2031"),
    ("IT", "ITALY",          "YA1234567", "ROSSI",    "MARCO",  "M", "25/06/1991", "25/06/2031"),
    ("KR", "KOREA REPUBLIC", "M12345678", "KIM",      "MINJUN", "M", "30/08/1989", "30/08/2029"),
]


def make_passport_image(
    code: str,
    country_name: str,
    passport_no: str,
    surname: str,
    given_name: str,
    sex: str,
    dob: str,
    expiry: str,
) -> Path:
    """Render a 600x400 passport-style fixture and save it under fixtures/."""
    img = Image.new("RGB", (600, 400), color=(245, 240, 230))
    draw = ImageDraw.Draw(img)

    f_title = ImageFont.truetype(FONT_BOLD_PATH, 26)
    f_field = ImageFont.truetype(FONT_PATH, 20)
    f_value = ImageFont.truetype(FONT_PATH, 22)

    # Title
    draw.text((30, 20), "PASSPORT", font=f_title, fill=(20, 20, 60))
    draw.text((30, 55), country_name, font=f_field, fill=(80, 80, 80))

    # Divider
    draw.line((30, 90, 570, 90), fill=(120, 120, 120), width=2)

    # Fields (label : value)
    y = 110
    rows = [
        ("PASSPORT NO", passport_no),
        ("SURNAME", surname),
        ("GIVEN NAME", given_name),
        ("SEX", sex),
        ("NATIONALITY", code),
        ("DATE OF BIRTH", dob),
        ("DATE OF EXPIRY", expiry),
    ]
    for label, val in rows:
        draw.text((30, y), f"{label}:", font=f_field, fill=(40, 40, 40))
        draw.text((230, y - 2), val, font=f_value, fill=(0, 0, 0))
        y += 38

    out_path = FIXTURE_DIR / f"sample_{code.lower()}_passport.jpg"
    img.save(out_path, "JPEG", quality=92)
    return out_path


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for row in COUNTRIES:
        p = make_passport_image(*row)
        size_kb = p.stat().st_size / 1024
        written.append(f"{p.name} ({size_kb:.1f}KB)")
    print("Generated fixtures:")
    for w in written:
        print(f"  {w}")


if __name__ == "__main__":
    main()
