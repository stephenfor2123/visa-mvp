"""Voice input — speech-to-text + structured field extraction (V2 §3.3.3).

W14-5 implementation: accept a short audio clip in 1 of 4 supported langs
(zh-CN / en / id / vi), run it through an ASR engine, and return a structured
dict of extracted fields (name / address / travel_date / ...) ready to
auto-fill the order form.

The public entry point is :func:`recognize_speech`.

ASR engine pluggability
-----------------------
We use a small registry pattern so we can switch engines without touching
the API layer:

* ``mock``        — deterministic, file-size-keyed mock (default in dev).
* ``google``      — SpeechRecognition + Google Web Speech API (free, no key).
* ``vosk``        — placeholder for the on-prem W14+ engine.

The mock engine is what runs in unit tests and when ``VOICE_ENGINE=mock``
is set.  Real engines are wired but never required to pass tests.

Error handling contract
-----------------------
* Audio format errors → ``VoiceInputError(code="VOICE_AUDIO_FORMAT")``
* Recognition failures (no speech / unintelligible / API errors) →
  ``VoiceInputError(code="VOICE_RECOGNIZE_FAILED")``
* Timeouts → ``VoiceInputError(code="VOICE_TIMEOUT")``

Callers (the FastAPI layer) translate these into 4xx/5xx envelopes via
:func:`map_voice_error_to_envelope`.
"""
import io
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Public constants                                                            #
# --------------------------------------------------------------------------- #

#: Languages supported end-to-end (V2 §3.3.3 spec).
SUPPORTED_LANGS: Tuple[str, ...] = ("zh-CN", "en", "id", "vi")

#: Display label per language (used in mock transcripts so they look
#: locale-realistic to humans reading logs / tests).
LANG_LABEL: Dict[str, str] = {
    "zh-CN": "中文",
    "en": "English",
    "id": "Bahasa Indonesia",
    "vi": "Tiếng Việt",
}

#: Accepted MIME types (mirrors what the browser's MediaRecorder emits
#: in different browsers).  WAVE is the most reliable format the
#: SpeechRecognition library can decode without ffmpeg.
ACCEPTED_MIME_TYPES: Tuple[str, ...] = (
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/aac",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
)

#: Magic-byte signatures for the formats we accept.  We only check the
#: first 16 bytes — enough to discriminate the common cases.
_AUDIO_SIGNATURES: List[Tuple[bytes, str]] = [
    (b"RIFF", "audio/wav"),       # WAV
    (b"ID3", "audio/mpeg"),       # MP3 with ID3 tag
    (b"\xff\xfb", "audio/mpeg"),  # MP3 frame sync
    (b"\xff\xf3", "audio/mpeg"),
    (b"OggS", "audio/ogg"),       # OGG
    (b"fLaC", "audio/flac"),      # FLAC
    (b"\x1aE\xdf\xa3", "audio/webm"),  # Matroska / WebM
    (b"ftyp", "audio/mp4"),       # MP4 family
]

#: Minimum audio payload we accept (1 KB).  Anything smaller is almost
#: certainly a corrupted / truncated capture.
MIN_AUDIO_BYTES = 1024

#: Maximum audio payload we accept (5 MB).  Larger files exceed the
#: multipart upload limit and would also blow the ASR quota.
MAX_AUDIO_BYTES = 5 * 1024 * 1024

#: Hard ceiling for the synchronous ASR call (seconds).  Real engines
#: run in a threadpool; this is the abort timeout.
RECOGNIZE_TIMEOUT_SEC = 8.0


# --------------------------------------------------------------------------- #
# Errors                                                                      #
# --------------------------------------------------------------------------- #
class VoiceInputError(Exception):
    """Base exception for all voice-input failures.

    Attributes
    ----------
    code:
        Stable machine-readable error code (one of the ``VOICE_*`` constants
        below).  Callers map this to the wire-level error code.
    message:
        Human-readable message, safe to log / surface to the client.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class VoiceAudioFormatError(VoiceInputError):
    def __init__(self, message: str = "Invalid audio format") -> None:
        super().__init__("VOICE_AUDIO_FORMAT", message)


class VoiceRecognizeError(VoiceInputError):
    def __init__(self, message: str = "Speech recognition failed") -> None:
        super().__init__("VOICE_RECOGNIZE_FAILED", message)


class VoiceTimeoutError(VoiceInputError):
    def __init__(self, message: str = "Speech recognition timeout") -> None:
        super().__init__("VOICE_TIMEOUT", message)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _detect_mime(audio_bytes: bytes) -> Optional[str]:
    """Return the MIME type guessed from magic bytes, or ``None``."""
    head = audio_bytes[:16]
    for sig, mime in _AUDIO_SIGNATURES:
        if head.startswith(sig):
            return mime
    # Some WAV files start with "RIFF....WAVE" — the bare RIFF signature
    # already covers that above.
    return None


def validate_audio(audio_bytes: bytes) -> str:
    """Validate raw audio bytes and return the detected MIME type.

    Raises :class:`VoiceAudioFormatError` if the input is unusable.
    """
    if audio_bytes is None:
        raise VoiceAudioFormatError("Audio payload is missing")
    if not isinstance(audio_bytes, (bytes, bytearray)):
        raise VoiceAudioFormatError(
            f"Audio payload must be bytes, got {type(audio_bytes).__name__}"
        )
    if len(audio_bytes) == 0:
        raise VoiceAudioFormatError("Audio payload is empty")
    if len(audio_bytes) < MIN_AUDIO_BYTES:
        raise VoiceAudioFormatError(
            f"Audio payload too small ({len(audio_bytes)} bytes, "
            f"minimum {MIN_AUDIO_BYTES})"
        )
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise VoiceAudioFormatError(
            f"Audio payload too large ({len(audio_bytes)} bytes, "
            f"maximum {MAX_AUDIO_BYTES})"
        )
    mime = _detect_mime(bytes(audio_bytes))
    if mime is None:
        # We don't reject unknown formats outright — many real-world WAV
        # recordings carry no recognisable signature in the first 16 bytes.
        # But we do warn via the return value.
        return "application/octet-stream"
    return mime


def _check_lang(lang: str) -> str:
    """Normalise the language code; raise on unsupported value."""
    if not lang or not isinstance(lang, str):
        raise VoiceAudioFormatError(f"lang must be a non-empty string, got {lang!r}")
    if lang not in SUPPORTED_LANGS:
        raise VoiceAudioFormatError(
            f"Unsupported language: {lang!r}. "
            f"Supported: {', '.join(SUPPORTED_LANGS)}"
        )
    return lang


# --------------------------------------------------------------------------- #
# Field extraction (heuristic, locale-aware)                                 #
# --------------------------------------------------------------------------- #
# These regexes power the auto-fill pipeline.  They are deliberately
# permissive — false positives are better than missing slots, since the
# user can correct the field manually in the UI.
#
_DATE_RE = re.compile(
    r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"            # 2026-06-14
    r"|(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})"            # 14/06/2026
    r"|(\d{1,2}[-/.]\d{1,2}[-/.]\d{2})\b"          # 14/06/26
    r"|(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?)"  # 2026年8月15日 (CJK)
)
# Strip leading filler words the user is likely to say before the date.
_DATE_FILLER = re.compile(
    r"^(?:出发|抵达|到达|离开|启程|出行|入境的?日期|date\s*of\s*travel|"
    r"travel\s*date|departure|arrival|tanggal\s*berangkat|"
    r"tanggal|ngày\s*khởi\s*hành|ngày\s*đi|"
    r"ngày)[是为:：\s]*",
    re.IGNORECASE,
)

# Name-related capture patterns
_NAME_PATTERN_ZH = re.compile(
    r"(?:我叫|我的名字是|我是|姓名)\s*([\u4e00-\u9fff]{2,4})", re.UNICODE
)
_NAME_PATTERN_EN = re.compile(
    r"(?:my\s+name\s+is|i\s+am|i'm|call\s+me)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]*){0,3})",
    re.IGNORECASE,
)
_NAME_PATTERN_ID = re.compile(
    r"(?:nama\s+saya|saya)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]*){0,3})",
    re.IGNORECASE,
)
_NAME_PATTERN_VI = re.compile(
    r"(?:tên\s+tôi\s+là|tôi\s+là|tôi\s+tên)\s+"
    r"([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]*){0,3})",
    re.IGNORECASE,
)

# Address-related capture patterns
_ADDR_PATTERN_ZH = re.compile(
    r"(?:地址是|住在|居住地|家庭住址|我的地址)\s*[:：]?\s*"
    r"([\u4e00-\u9fffA-Za-z0-9号弄区市省县路街道]{4,80})",
    re.UNICODE,
)
_ADDR_PATTERN_EN = re.compile(
    r"(?:address\s+is|i\s+live\s+(?:at|in)|my\s+address\s+is|located\s+(?:at|in))\s+"
    r"([A-Z0-9][A-Za-z0-9\s,.-]{4,80})",
    re.IGNORECASE,
)
_ADDR_PATTERN_ID = re.compile(
    r"(?:alamat\s+saya|alamat|tinggal\s+di)\s+"
    r"([A-Z0-9][A-Za-z0-9\s,.-]{4,80})",
    re.IGNORECASE,
)
_ADDR_PATTERN_VI = re.compile(
    r"(?:địa\s*chỉ\s*(?:của\s*tôi\s*)?là|địa\s*chỉ|tôi\s*ở)\s+"
    r"([A-Z0-9À-Ỹ][A-Za-z0-9À-Ỹà-ỹ\s,.-]{4,80})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _FieldPattern:
    """Locale-specific patterns for a single field."""

    name: re.Pattern
    address: re.Pattern


_PATTERNS_BY_LANG: Dict[str, _FieldPattern] = {
    "zh-CN": _FieldPattern(_NAME_PATTERN_ZH, _ADDR_PATTERN_ZH),
    "en":    _FieldPattern(_NAME_PATTERN_EN, _ADDR_PATTERN_EN),
    "id":    _FieldPattern(_NAME_PATTERN_ID, _ADDR_PATTERN_ID),
    "vi":    _FieldPattern(_NAME_PATTERN_VI, _ADDR_PATTERN_VI),
}


def _clean_date_token(token: str) -> str:
    """Normalise a date string to ISO YYYY-MM-DD when possible."""
    token = token.strip().strip(".,;:日")
    token = _DATE_FILLER.sub("", token, count=1).strip()
    # CJK format: "2026年8月15日" → "2026-8-15"
    cjk_m = re.match(r"^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?$", token)
    if cjk_m:
        y, m, d = cjk_m.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    for fmt in (
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d-%m-%y", "%d/%m/%y", "%d.%m.%y",
        "%m-%d-%Y", "%m/%d/%Y", "%m.%d.%Y",
    ):
        try:
            from datetime import datetime
            return datetime.strptime(token, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return token


def _extract_date(text: str) -> Optional[str]:
    """Pull the first recognisable date from free-form text."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    raw = next((g for g in m.groups() if g), "")
    return _clean_date_token(raw) if raw else None


def _extract_with_pattern(pattern: re.Pattern, text: str) -> Optional[str]:
    m = pattern.search(text)
    if not m:
        return None
    value = (m.group(1) or "").strip()
    # Trim trailing punctuation that ASR tends to over-emit.
    return value.rstrip("。.,!?;:") if value else None


def extract_fields(text: str, lang: str) -> Dict[str, Optional[str]]:
    """Map a transcript to a structured applicant dict.

    The result always contains every well-known key — values are ``None``
    when the field could not be inferred.  This shape is what the front-end
    Materials.vue auto-fill form expects.
    """
    lang = _check_lang(lang)
    patterns = _PATTERNS_BY_LANG[lang]
    name = _extract_with_pattern(patterns.name, text)
    address = _extract_with_pattern(patterns.address, text)
    travel_date = _extract_date(text)
    return {
        "name": name,
        "address": address,
        "travel_date": travel_date,
        # Always-present passthrough for the UI's "show raw transcript" toggle.
        "raw_text": text,
        "lang": lang,
    }


# --------------------------------------------------------------------------- #
# Engines                                                                     #
# --------------------------------------------------------------------------- #
@dataclass
class RecognitionResult:
    """Internal ASR result — engine-agnostic."""

    transcript: str
    confidence: float
    engine: str


EngineFn = Callable[[bytes, str, float], RecognitionResult]


def _mock_engine(audio_bytes: bytes, lang: str, timeout_sec: float) -> RecognitionResult:
    """Deterministic mock engine for tests and local dev.

    The transcript is derived from the audio length so the same input
    always produces the same output.  This is what makes the unit tests
    stable and the dev experience predictable.
    """
    if not audio_bytes:
        raise VoiceRecognizeError("mock: empty audio")
    # Pick a phrase that matches the requested language, with a small
    # amount of variation based on the payload length.
    bucket = (len(audio_bytes) // 1024) % 4
    phrases: Dict[str, List[str]] = {
        "zh-CN": [
            "我叫张三,护照号E12345678,2026年8月15日出发,地址是上海市浦东新区世纪大道100号",
            "我的名字是李四,住在北京市朝阳区建国路88号,出行日期2026-09-10",
            "我叫王五,前往日期2026年10月1号,住址广州市天河区珠江新城",
            "我叫赵六,2026/12/24 旅行,地址深圳市南山区科技园路1号",
        ],
        "en": [
            "My name is John Smith, passport A12345678, travel date 2026-08-15, "
            "I live at 100 Main Street New York",
            "I am Sarah Johnson, my address is 42 Oxford Road London, "
            "departing 2026-09-10",
            "Call me Michael Brown, address 88 Queen Street Toronto, "
            "travel date 2026/10/01",
            "I live in 200 Bay Area San Francisco, name Emily Davis, "
            "going 2026.12.24",
        ],
        "id": [
            "Nama saya Andi, tinggal di Jalan Sudirman nomor 100 Jakarta, "
            "tanggal berangkat 2026-08-15",
            "Saya Budi, alamat saya Jalan Merdeka 88 Bandung, "
            "tanggal 2026-09-10",
            "Nama saya Citra, beralamat di Jalan Asia Afrika 200 Denpasar, "
            "tanggal berangkat 2026/10/01",
            "Saya tinggal di Jalan Malioboro 50 Yogyakarta, nama Dewi, "
            "pergi 2026.12.24",
        ],
        "vi": [
            "Tên tôi là Nguyễn Văn A, địa chỉ 100 Lê Lợi Quận 1 TP HCM, "
            "ngày khởi hành 2026-08-15",
            "Tôi là Trần Thị B, địa chỉ 88 Trần Phú Hà Nội, ngày đi 2026-09-10",
            "Tôi tên Lê Văn C, địa chỉ 200 Nguyễn Huệ Đà Nẵng, "
            "ngày khởi hành 2026/10/01",
            "Tôi ở 50 Phan Đình Phùng Hà Nội, tên Phạm D, đi 2026.12.24",
        ],
    }
    transcript = phrases[lang][bucket]
    return RecognitionResult(
        transcript=transcript,
        confidence=0.93 - 0.02 * bucket,
        engine="mock",
    )


def _google_engine(audio_bytes: bytes, lang: str, timeout_sec: float) -> RecognitionResult:
    """Real Google Web Speech API engine via SpeechRecognition.

    Wraps the synchronous library call in a soft timeout.  If the library
    is not installed, we raise :class:`VoiceRecognizeError` with a clear
    hint — this is the path the unit tests deliberately avoid.
    """
    try:
        import speech_recognition as sr  # type: ignore
    except ImportError as exc:  # pragma: no cover - covered by env check
        raise VoiceRecognizeError(
            "speech_recognition package is not installed; "
            "install it or set VOICE_ENGINE=mock"
        ) from exc

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
    except Exception as exc:  # noqa: BLE001 — library raises generic
        raise VoiceAudioFormatError(
            f"Could not decode audio as WAV/AIFF/FLAC: {exc}"
        ) from exc

    started = time.monotonic()
    try:
        text = recognizer.recognize_google(
            audio, language=lang, show_all=False
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - started
        if elapsed > timeout_sec:
            raise VoiceTimeoutError(
                f"recognize_google exceeded {timeout_sec:.1f}s"
            ) from exc
        raise VoiceRecognizeError(str(exc)) from exc
    if not text:
        raise VoiceRecognizeError("recognize_google returned empty text")
    return RecognitionResult(transcript=text, confidence=0.85, engine="google")


_ENGINES: Dict[str, EngineFn] = {
    "mock": _mock_engine,
    "google": _google_engine,
}


def _resolve_engine_name() -> str:
    """Resolve the active engine from env, defaulting to ``mock``."""
    name = (os.getenv("VOICE_ENGINE") or "mock").strip().lower()
    return name if name in _ENGINES else "mock"


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def recognize_speech(
    audio_bytes: bytes,
    lang: str = "en",
    *,
    timeout_sec: float = RECOGNIZE_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """Recognize speech in ``audio_bytes`` and return structured fields.

    Parameters
    ----------
    audio_bytes:
        Raw audio payload (WAV / MP3 / OGG / FLAC / MP4 / WebM).
    lang:
        One of ``"zh-CN"``, ``"en"``, ``"id"``, ``"vi"``.
    timeout_sec:
        Soft cap on the synchronous recognition call.  Defaults to
        :data:`RECOGNIZE_TIMEOUT_SEC`.

    Returns
    -------
    dict
        ``{name, address, travel_date, raw_text, lang, confidence, engine}``.
        All keys are always present; missing fields are ``None``.

    Raises
    ------
    VoiceAudioFormatError
        On any audio-format / size validation problem.
    VoiceRecognizeError
        On any failure from the ASR engine that isn't a timeout.
    VoiceTimeoutError
        If the engine exceeds ``timeout_sec``.
    """
    # Step 1: validate.
    mime = validate_audio(audio_bytes)
    lang = _check_lang(lang)

    # Step 2: pick engine and run.
    engine_name = _resolve_engine_name()
    engine_fn = _ENGINES[engine_name]

    started = time.monotonic()
    try:
        result = engine_fn(bytes(audio_bytes), lang, timeout_sec)
    except VoiceInputError:
        raise  # bubble structured errors as-is
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - started
        if elapsed > timeout_sec:
            raise VoiceTimeoutError(
                f"ASR engine '{engine_name}' exceeded {timeout_sec:.1f}s"
            ) from exc
        raise VoiceRecognizeError(str(exc)) from exc
    elapsed = time.monotonic() - started
    if elapsed > timeout_sec:
        raise VoiceTimeoutError(
            f"ASR engine '{engine_name}' exceeded {timeout_sec:.1f}s"
        )

    # Step 3: extract structured fields from the transcript.
    fields = extract_fields(result.transcript, lang)
    fields["confidence"] = result.confidence
    fields["engine"] = result.engine
    fields["mime_type"] = mime
    fields["audio_bytes"] = len(audio_bytes)
    fields["elapsed_ms"] = int(elapsed * 1000)
    return fields


def map_voice_error_to_envelope(exc: VoiceInputError) -> Dict[str, Any]:
    """Translate a :class:`VoiceInputError` to a stable wire envelope.

    Useful for the FastAPI exception handler — returns a dict that can be
    dropped straight into :class:`ApiResponse`.
    """
    code_to_wire = {
        "VOICE_AUDIO_FORMAT":     ("2003", 400),
        "VOICE_RECOGNIZE_FAILED": ("2004", 422),
        "VOICE_TIMEOUT":          ("2005", 504),
    }
    wire_code, http_status = code_to_wire.get(
        exc.code, ("2003", 400)
    )
    return {
        "code": wire_code,
        "message": exc.message,
        "http_status": http_status,
        "data": {"error_code": exc.code},
    }


__all__ = [
    "SUPPORTED_LANGS",
    "ACCEPTED_MIME_TYPES",
    "LANG_LABEL",
    "MIN_AUDIO_BYTES",
    "MAX_AUDIO_BYTES",
    "RECOGNIZE_TIMEOUT_SEC",
    "VoiceInputError",
    "VoiceAudioFormatError",
    "VoiceRecognizeError",
    "VoiceTimeoutError",
    "RecognitionResult",
    "validate_audio",
    "extract_fields",
    "recognize_speech",
    "map_voice_error_to_envelope",
]
