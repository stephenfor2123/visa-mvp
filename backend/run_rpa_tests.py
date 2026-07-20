#!/usr/bin/env python3
"""
Standalone test runner for RPA modules.
Bypasses app package init which triggers SQLAlchemy hang.
Uses direct file loading to import modules in isolation.
"""
import sys
import importlib.util
from pathlib import Path

BASE = Path("/Users/apple/Desktop/签证项目/backend")

def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

# ── Setup fake package hierarchy ──────────────────────────────────────────────
import types
for pkg in ["app", "app.core", "app.services", "app.services.rpa", "app.services.rpa.providers"]:
    if pkg not in sys.modules:
        sys.modules[pkg] = types.ModuleType(pkg)

sys.modules["app.core"].config = load_file("app.core.config", BASE / "app/core/config.py")

# ── Load RPA modules ──────────────────────────────────────────────────────────
captcha_solver = load_file("app.services.rpa.captcha_solver", BASE / "app/services/rpa/captcha_solver.py")
page_parser    = load_file("app.services.rpa.page_parser",    BASE / "app/services/rpa/page_parser.py")
form_filler    = load_file("app.services.rpa.form_filler",    BASE / "app/services/rpa/form_filler.py")
rpa_scheduler  = load_file("app.services.rpa.rpa_scheduler",  BASE / "app/services/rpa/rpa_scheduler.py")
providers_base = load_file("app.services.rpa.providers.base", BASE / "app/services/rpa/providers/base.py")
indonesia_visa = load_file("app.services.rpa.providers.IndonesiaVisa", BASE / "app/services/rpa/providers/IndonesiaVisa.py")
vietnam_visa   = load_file("app.services.rpa.providers.VietnamVisa",   BASE / "app/services/rpa/providers/VietnamVisa.py")

# Expose classes
CaptchaSolver    = captcha_solver.CaptchaSolver
CaptchaSolverError = captcha_solver.CaptchaSolverError
PageParser       = page_parser.PageParser
FormField        = page_parser.FormField
FormSpec         = page_parser.FormSpec
CaptchaInfo      = page_parser.CaptchaInfo
FormFiller       = form_filler.FormFiller
FormFillerError  = form_filler.FormFillerError
RPAScheduler     = rpa_scheduler.RPAScheduler
TaskStatus       = rpa_scheduler.TaskStatus
RPATask         = rpa_scheduler.RPATask
BaseVisaProvider = providers_base.BaseVisaProvider
IndonesiaVisaProvider = indonesia_visa.IndonesiaVisaProvider
VietnamVisaProvider   = vietnam_visa.VietnamVisaProvider

# ── Test helpers ──────────────────────────────────────────────────────────────
passed = failed = 0

def assert_equal(a, b, msg=""):
    global passed, failed
    if a == b:
        passed += 1
        print(f"  ✓ {msg or f'{a!r} == {b!r}'}")
    else:
        failed += 1
        print(f"  ✗ {msg or f'{a!r} == {b!r}'}  (got {a!r})")

def assert_true(x, msg=""):
    global passed, failed
    if x:
        passed += 1
        print(f"  ✓ {msg}")
    else:
        failed += 1
        print(f"  ✗ {msg}  (got {x!r})")

def assert_in(a, b, msg=""):
    global passed, failed
    if a in b:
        passed += 1
        print(f"  ✓ {msg or f'{a!r} in {b!r}'}")
    else:
        failed += 1
        print(f"  ✗ {msg or f'{a!r} in {b!r}'}")

def assert_is_instance(a, b, msg=""):
    global passed, failed
    if isinstance(a, b):
        passed += 1
        print(f"  ✓ {msg or f'isinstance({a!r}, {b!r})'}")
    else:
        failed += 1
        print(f"  ✗ {msg or f'isinstance({a!r}, {b!r})'}  (got {type(a)!r})")

def assert_raises(fn, exc_type, msg=""):
    global passed, failed
    try:
        fn()
        failed += 1
        print(f"  ✗ {msg}  (no exception raised)")
    except exc_type:
        passed += 1
        print(f"  ✓ {msg}")
    except Exception as e:
        failed += 1
        print(f"  ✗ {msg}  (wrong exception: {e})")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST: test_rpa_captcha_solver")
print("="*70)

solver = CaptchaSolver()
assert_equal(solver._max_retries, 3, "_max_retries defaults to 3")
assert_equal(solver.engine.value, "pytesseract", "engine defaults to pytesseract")
import pytesseract as pyt
assert_true(callable(pyt.image_to_string), "pytesseract.image_to_string is callable")

# Create a minimal valid PNG image (1x1 pixel) for testing
from PIL import Image
import io
img = Image.new("RGB", (50, 20), color="white")
buf = io.BytesIO()
img.save(buf, format="PNG")
valid_png_bytes = buf.getvalue()
result = solver.solve_captcha(valid_png_bytes)
assert_true(isinstance(result, str), "solve_captcha returns string")

# After 3 consecutive failures, raise CaptchaSolverError
solver._consecutive_failures = 0
solver._max_retries = 1
assert_raises(lambda: solver.solve_captcha(b"not an image"), CaptchaSolverError,
              "max retry exhaustion raises CaptchaSolverError")
solver._max_retries = 3  # restore

assert_true(callable(solver.solve_slider_captcha), "solve_slider_captcha is callable")
result_slider = solver.solve_slider_captcha("http://example.com/slider.png", "http://example.com/target.png", 0.5)
assert_equal(result_slider["distance"], 0.5, "slider result distance matches")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST: test_rpa_page_parser")
print("="*70)

parser = PageParser()

html_with_form = """<!DOCTYPE html>
<html><body>
<form id="visaForm" action="/submit" method="POST">
  <input type="text" name="fullName" />
  <input type="date" name="birthDate" />
  <select name="nationality">
    <option value="CN">China</option>
  </select>
  <input type="file" name="passportPhoto" />
</form>
</body></html>"""
fields = parser.parse_form_fields(html_with_form)
assert_in("fullName", fields, "fullName field found")
assert_equal(fields["fullName"], "text", "fullName type is text")
assert_in("birthDate", fields, "birthDate field found")
assert_equal(fields["birthDate"], "date", "birthDate type is date")
assert_in("nationality", fields, "nationality field found")
assert_equal(fields["nationality"], "select", "nationality type is select")
assert_in("passportPhoto", fields, "passportPhoto field found")
assert_equal(fields["passportPhoto"], "file", "passportPhoto type is file")

html_with_captcha = """<html><body>
<img id="captchaImg" src="/captcha.png" />
<input type="text" name="captchaCode" />
<script>滑块验证</script>
</body></html>"""
captcha_info = parser.parse_captcha_location(html_with_captcha)
assert_equal(captcha_info["type"], "image", "captcha type detected")
assert_equal(captcha_info["image_url"], "/captcha.png", "image URL extracted")

captcha_info2 = parser.parse_captcha_location("<html><body>no captcha</body></html>")
assert_equal(captcha_info2["type"], "none", "no captcha returns type=none")

assert_true(callable(parser.parse_form_fields), "parse_form_fields is callable")
print("  ✓ PageParser methods are callable")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST: test_rpa_form_filler")
print("="*70)

filler = FormFiller()
assert_is_instance(filler._mapping, dict, "mappings loaded from YAML")
countries = filler.get_supported_countries()
assert_in("ID", countries, "Indonesia country loaded")
assert_in("VN", countries, "Vietnam country loaded")

passport = {
    "surname": "Zhang",
    "given_names": "San",
    "passport_number": "E1234567",
    "nationality": "CN",
    "birth_date": "1990-01-15",
    "gender": "M",
    "issue_date": "2020-03-01",
    "expiry_date": "2030-03-01",
    "issue_place": "Beijing",
}
mapped = filler.map_fields(passport, "ID")
assert_equal(mapped["fullname"], "Zhang San", "fullname mapped correctly")
assert_equal(mapped["passportno"], "E1234567", "passport number mapped")
assert_equal(mapped["nationality"], "Chinese", "nationality mapped to English")
assert_equal(mapped["birthday"], "15/01/1990", "birth date DD/MM/YYYY format")
assert_equal(mapped["sex"], "M", "gender M maps to M")

mapped_vn = filler.map_fields(passport, "VN")
assert_equal(mapped_vn["fullName"], "Zhang San", "Vietnam: fullName")
assert_equal(mapped_vn["passportNumber"], "E1234567", "Vietnam: passportNumber")
assert_equal(mapped_vn["nationality"], "Chinese", "Vietnam: nationality translated to English")
assert_equal(mapped_vn["birthDate"], "15/01/1990", "Vietnam: birth date DD/MM/YYYY")

assert_raises(lambda: filler.map_fields(passport, "XX"), FormFillerError,
              "Unknown country_code raises FormFillerError")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("TEST: test_rpa_scheduler")
print("="*70)

scheduler = RPAScheduler()
cfg = scheduler.get_config()
assert_equal(cfg["rate_limits"]["ip_per_day"], 50, "ip_per_day default 50")
assert_equal(cfg["rate_limits"]["account_interval_minutes"], 30, "account_interval_minutes default 30")
assert_equal(cfg["rate_limits"]["max_concurrent_tasks"], 2, "max_concurrent_tasks default 2")

# submit_visa_application requires country_code and visa_type
task_id = scheduler.submit_visa_application(
    order_id="order-001",
    country_code="US",
    visa_type="B211A",
    user_id="user-test",
    ip_address="127.0.0.1",
)
assert_true(task_id.startswith("rpa-"), "task_id starts with rpa-")
# Access internal task store via get_task_status
status = scheduler.get_task_status(task_id)
assert_equal(status["status"], "submitting", "new task is submitting")
assert_in("progress", status, "progress field present")
assert_in("message", status, "message field present")

cancel_result = scheduler.cancel_task(task_id)
assert_equal(cancel_result["status"], "cancelled", "cancel returns cancelled status")
assert_equal(cancel_result["message"], "Cancelled by user", "cancellation message")

status2 = scheduler.get_task_status(task_id)
assert_equal(status2["status"], "cancelled", "get_task_status after cancel is cancelled")

# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
total = passed + failed
print(f"\nPassed: {passed}/{total}")
print(f"Failed: {failed}/{total}")
if failed == 0:
    print("\n✓ ALL TESTS PASSED")
    sys.exit(0)
else:
    print("\n✗ SOME TESTS FAILED")
    sys.exit(1)