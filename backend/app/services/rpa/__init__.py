"""
RPA Service package — visa website automation core.

Modules:
  captcha_solver   — OCR-based captcha recognition (pytesseract / third-party API)
  page_parser      — HTML form parsing and captcha element extraction
  form_filler      — Passport field mapping and form submission
  rpa_scheduler    — Task state machine, rate limiting, and orchestration

Providers:
  Historical IndonesiaVisa / VietnamVisa files remain under providers/ for
  reference but are NOT registered — ID/VN are customer markets, not
  destinations (docs/PRODUCT_SCOPE.md).
"""
from app.services.rpa.captcha_solver import CaptchaSolver, CaptchaSolverError
from app.services.rpa.form_filler import FormFiller, FormFillerError, FormSubmitResult
from app.services.rpa.page_parser import CaptchaInfo, FormField, FormSpec, PageParser
from app.services.rpa.rpa_scheduler import (
    RateLimitExceeded,
    RPAScheduler,
    RPASchedulerError,
    RPATask,
    TaskStatus,
)

__all__ = [
    # Captcha
    "CaptchaSolver",
    "CaptchaSolverError",
    # Page parser
    "CaptchaInfo",
    "FormField",
    "FormSpec",
    "PageParser",
    # Form filler
    "FormFiller",
    "FormFillerError",
    "FormSubmitResult",
    # Scheduler
    "RateLimitExceeded",
    "RPAScheduler",
    "RPASchedulerError",
    "RPATask",
    "TaskStatus",
]