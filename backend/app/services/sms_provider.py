"""B-W6-1 — Standalone SMS provider (V2 §6.1, Mock-only for V2).

Scope:
  - `SmsProvider` ABC (3 methods: send_sms / verify_code / get_template)
  - `MockSmsProvider` — the only implementation in V2 (no Tencent / Twilio /
    Aliyun SDK is wired in V2; that lands in V2.1).
  - In-memory dict keyed by `(phone, purpose)` storing `(code, expires_at)`.
  - Zero credentials: no TENCENT_*, no TWILIO_*, no ALIYUN_* env vars.
  - `send_sms` prints the code to stdout (loguru + plain stdout) so the
    frontend dev-mode can autofill, mirroring the W4 SmsService mock echo.

Coexistence with the W4 `SmsService` (DB-backed):
  - `SmsService` is consumed by `/api/v2/auth/*` for register/login flows.
  - `SmsProvider` is consumed by the new `/api/v2/sms/*` standalone routes
    added in W6-1, which are what the front-end dev console will hit when
    it polls for "test SMS".
  - Both live behind their own ABC; the V2.1 swap is additive — drop in a
    `TencentSmsProvider` implementing the same ABC.
"""
import random
import secrets
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from loguru import logger


_log = logger.bind(component="sms_provider")
_VALID_PURPOSES = ("register", "login", "reset", "destroy")


# --------------------------------------------------------------------------- #
# Errors (kept module-local — these are provider errors, not Biz errors).    #
# Catching callers should re-raise as BizException(ErrorCode.SMS_*) if they  #
# want the V2 envelope; the standalone /api/v2/sms/* routes do that below.   #
# --------------------------------------------------------------------------- #
class SmsProviderError(Exception):
    """Base for provider-level errors."""


class CodeExpired(SmsProviderError):
    """Stored code was past its TTL."""


class CodeMismatch(SmsProviderError):
    """Stored code did not match input."""


class NoCodeOnFile(SmsProviderError):
    """No code was previously issued for this (phone, purpose)."""


# --------------------------------------------------------------------------- #
# Data class for stored codes                                                 #
# --------------------------------------------------------------------------- #
@dataclass
class _StoredCode:
    code: str
    expires_at: float           # monotonic seconds since epoch
    message_id: str
    phone: str
    phone_country: str
    purpose: str
    created_at: datetime       # wall-clock — used in MessageStatus


# --------------------------------------------------------------------------- #
# Abstract base                                                              #
# --------------------------------------------------------------------------- #
class SmsProvider(ABC):
    """Single ABC — independent of the W4 SMSChannel ABC on purpose so the
    V2.1 Tencent swap can land without rewriting callers."""

    @abstractmethod
    async def send_sms(
        self,
        phone: str,
        phone_country: str,
        purpose: str,
    ) -> dict:
        """Generate & store a 6-digit OTP for `(phone, purpose)`.

        Returns a dict:
            {
              "ok": True,
              "message_id": str,
              "code": str,                  # raw 6-digit code (mock echo)
              "expires_in": int,            # seconds (mock: 300)
            }
        Implementations should NOT raise on transient gateway failures —
        return `ok=False` with `error` instead.
        """
        raise NotImplementedError

    @abstractmethod
    async def verify_code(
        self,
        phone: str,
        phone_country: str,
        code: str,
        purpose: str,
    ) -> bool:
        """Return True iff the stored code matches AND is not expired AND
        has not been used yet.

        Raises:
            NoCodeOnFile — no OTP was ever issued for this (phone, purpose)
            CodeMismatch — issued code does not match
            CodeExpired  — issued code past TTL
        """
        raise NotImplementedError

    @abstractmethod
    async def get_template(self, purpose: str, locale: str = "zh-CN") -> str:
        """Return the localized message body for a given purpose."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mock implementation (V2 default)                                            #
# --------------------------------------------------------------------------- #
class MockSmsProvider(SmsProvider):
    """In-process mock. No external deps, no creds, no network.

    Storage: a single in-memory dict protected by a `threading.Lock` so
    concurrent tests don't trip on each other. (We are async, but pytest
    defaults to one event loop per test, so the lock is for paranoia.)

    Code lifetime: `ttl_seconds` (default 300, matches W4 SmsService).
    """

    DEFAULT_TTL = 300
    DEFAULT_CODE_LEN = 6

    def __init__(self, ttl_seconds: int = DEFAULT_TTL, code_length: int = DEFAULT_CODE_LEN) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if code_length < 4 or code_length > 8:
            raise ValueError("code_length must be between 4 and 8")
        self._ttl = ttl_seconds
        self._code_length = code_length
        self._store: dict[tuple[str, str], _StoredCode] = {}
        self._lock = threading.Lock()
        # Template registry (mutable — /template endpoint adds entries)
        self._templates: dict[tuple[str, str], str] = {
            ("register", "zh-CN"): "【签证帮】您的注册验证码为 {code},5 分钟内有效。",
            ("login", "zh-CN"): "【签证帮】您的登录验证码为 {code},5 分钟内有效。",
            ("reset", "zh-CN"): "【签证帮】您的重置密码验证码为 {code},5 分钟内有效。",
            ("destroy", "zh-CN"): "【签证帮】您的销户验证码为 {code},5 分钟内有效。",
            ("register", "en-US"): "[VisaGo] Your sign-up code is {code}, valid for 5 minutes.",
            ("login", "en-US"): "[VisaGo] Your login code is {code}, valid for 5 minutes.",
            ("reset", "en-US"): "[VisaGo] Your password-reset code is {code}, valid for 5 minutes.",
            ("destroy", "en-US"): "[VisaGo] Your account-deletion code is {code}, valid for 5 minutes.",
        }

    # ------------------------------------------------------------------ #
    # helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _gen_code(length: int) -> str:
        """Cryptographically-random numeric code with leading-zero padding.

        Uses `secrets` so test runs cannot accidentally share prefixes.
        """
        upper = 10 ** length
        return f"{secrets.randbelow(upper):0{length}d}"

    def _now_mono(self) -> float:
        return time.monotonic()

    def _now_wall(self) -> datetime:
        return datetime.now(timezone.utc)

    def _key(self, phone: str, purpose: str) -> tuple[str, str]:
        return (phone, purpose)

    def _purge_expired_unlocked(self) -> None:
        """Caller holds the lock."""
        now_mono = self._now_mono()
        stale = [k for k, v in self._store.items() if v.expires_at <= now_mono]
        for k in stale:
            del self._store[k]

    # ------------------------------------------------------------------ #
    # SmsProvider ABC                                                    #
    # ------------------------------------------------------------------ #
    async def send_sms(
        self,
        phone: str,
        phone_country: str,
        purpose: str,
    ) -> dict:
        if purpose not in _VALID_PURPOSES:
            return {"ok": False, "error": f"invalid purpose: {purpose}"}

        code = self._gen_code(self._code_length)
        message_id = f"mock_{int(time.time() * 1000)}_{secrets.token_hex(4)}"
        expires_at = self._now_mono() + self._ttl
        now_wall = self._now_wall()

        with self._lock:
            self._purge_expired_unlocked()
            self._store[self._key(phone, purpose)] = _StoredCode(
                code=code,
                expires_at=expires_at,
                message_id=message_id,
                phone=phone,
                phone_country=phone_country,
                purpose=purpose,
                created_at=now_wall,
            )

        # Loud console.log so dev / E2E / curl can grab the code.
        ts = now_wall.isoformat(timespec="seconds")
        line = (
            f"{ts} [SMS-MOCK] phone={phone_country}{phone} "
            f"code={code} purpose={purpose} message_id={message_id}"
        )
        print(line)               # plain stdout — matches the spec verbatim
        _log.info(line)

        return {
            "ok": True,
            "message_id": message_id,
            "code": code,
            "expires_in": self._ttl,
        }

    async def verify_code(
        self,
        phone: str,
        phone_country: str,
        code: str,
        purpose: str,
    ) -> bool:
        # Defense in depth — DTO validator already gates this, but the
        # provider is also reachable from non-HTTP callers (tests, jobs).
        if not (isinstance(code, str) and code.isdigit() and len(code) == self._code_length):
            raise CodeMismatch("code must be 6 digits")

        key = self._key(phone, purpose)
        with self._lock:
            stored = self._store.get(key)
            if stored is None:
                # Could be: never issued, already used, or purged by a
                # prior expired-cleanup. Distinguish "actually expired
                # on this call" by re-checking the (now-empty) slot via
                # the _purge_expired_unlocked side effect below.
                self._purge_expired_unlocked()
                raise NoCodeOnFile(f"no OTP on file for {phone}/{purpose}")
            # Snapshot expiry first — if we purge-then-check we'd lose
            # the distinction between "never sent" (2002) and "expired"
            # (2008) which the API contract requires.
            if stored.expires_at <= self._now_mono():
                del self._store[key]
                raise CodeExpired(f"code for {phone}/{purpose} expired")
            if stored.code != code:
                raise CodeMismatch("code mismatch")
            # One-shot: invalidate on successful verify so the same OTP
            # can't be reused for a second /sms/verify call.
            del self._store[key]
            return True

    async def get_template(self, purpose: str, locale: str = "zh-CN") -> str:
        if purpose not in _VALID_PURPOSES and purpose != "generic":
            raise ValueError(f"invalid purpose: {purpose}")
        body = self._templates.get((purpose, locale))
        if body is None:
            # Fall back to generic English if locale not registered.
            body = self._templates.get((purpose, "en-US")) or self._templates.get(("login", "en-US"))
        return body or "【签证帮】您的验证码为 {code}。"

    # ------------------------------------------------------------------ #
    # template registration (V2.1 ready, mock-only in V2)                #
    # ------------------------------------------------------------------ #
    def register_template(self, template_id: str, purpose: str, locale: str, body: str) -> None:
        """In-memory template registry update. Replaces if (purpose, locale) already set."""
        if purpose not in (*_VALID_PURPOSES, "generic"):
            raise ValueError(f"invalid purpose: {purpose}")
        self._templates[(purpose, locale)] = body
        _log.info("registered sms template id={} purpose={} locale={}", template_id, purpose, locale)

    def get_message_status(self, message_id: str) -> Optional[dict]:
        """Mock-side read — used by GET /api/v2/sms/{message_id}."""
        with self._lock:
            for stored in self._store.values():
                if stored.message_id == message_id:
                    return {
                        "message_id": stored.message_id,
                        "status": "sent",
                        "phone": stored.phone,
                        "phone_country": stored.phone_country,
                        "purpose": stored.purpose,
                        "sent_at": stored.created_at.isoformat(timespec="seconds"),
                    }
        # Either expired/used or never existed — mock always says "sent"
        # for issued IDs that haven't expired, "unknown" otherwise.
        return {
            "message_id": message_id,
            "status": "unknown",
        }


# --------------------------------------------------------------------------- #
# Factory — single source of truth                                            #
# --------------------------------------------------------------------------- #
_provider_singleton: Optional[SmsProvider] = None
_provider_lock = threading.Lock()


def get_sms_provider() -> SmsProvider:
    """Return the process-wide MockSmsProvider (V2 default).

    V2.1 swap: read `settings.sms_provider_kind`, return `TencentSmsProvider`
    if "tencent" is set. For V2 we hard-code mock to satisfy the
    "零凭据 / 1 天可跑" rule.
    """
    global _provider_singleton
    with _provider_lock:
        if _provider_singleton is None:
            _provider_singleton = MockSmsProvider()
        return _provider_singleton


def reset_sms_provider_for_tests() -> None:
    """Drop the singleton — used by pytest to start each test with a clean store."""
    global _provider_singleton
    with _provider_lock:
        _provider_singleton = None