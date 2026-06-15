"""Unit tests for backend/app/services/voice_input.py — W14-5.

Tests:
1. Audio format validation (size + magic bytes)
2. Language validation
3. recognize_speech() happy path for all 4 supported languages
4. recognize_speech() invalid audio format
5. recognize_speech() timeout
6. extract_fields() heuristic correctness (zh / en / id / vi)
7. map_voice_error_to_envelope() wire code mapping

This test file loads ``app/services/voice_input.py`` directly via
importlib to avoid the ``app.services.__init__`` package side-effects
(pydantic_core architecture mismatch on this host).  The voice service
itself has zero ``app.*`` imports, so this is a clean standalone test.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import time
import wave
from pathlib import Path

import pytest


# ---------------------------------------------------------------- #
# Module loader — load the service file directly to avoid          #
# triggering the heavy app.services package init.                  #
# ---------------------------------------------------------------- #
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_VOICE_PATH = _BACKEND_ROOT / "app" / "services" / "voice_input.py"


def _load_voice_module():
    """Load the voice_input service module without going through app.services.

    The service file has no ``app.*`` imports, so we can load it in isolation.
    We register it in ``sys.modules`` first so the ``@dataclass`` decorator
    can resolve ``cls.__module__`` for ``from __future__ import annotations``.
    """
    spec = importlib.util.spec_from_file_location(
        "app_services_voice_input", _VOICE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["app_services_voice_input"] = mod
    spec.loader.exec_module(mod)
    return mod


voice_input = _load_voice_module()


# Pull the public names we need into the test namespace.
ACCEPTED_MIME_TYPES = voice_input.ACCEPTED_MIME_TYPES
LANG_LABEL = voice_input.LANG_LABEL
MAX_AUDIO_BYTES = voice_input.MAX_AUDIO_BYTES
MIN_AUDIO_BYTES = voice_input.MIN_AUDIO_BYTES
RECOGNIZE_TIMEOUT_SEC = voice_input.RECOGNIZE_TIMEOUT_SEC
SUPPORTED_LANGS = voice_input.SUPPORTED_LANGS
VoiceAudioFormatError = voice_input.VoiceAudioFormatError
VoiceInputError = voice_input.VoiceInputError
VoiceRecognizeError = voice_input.VoiceRecognizeError
VoiceTimeoutError = voice_input.VoiceTimeoutError
extract_fields = voice_input.extract_fields
map_voice_error_to_envelope = voice_input.map_voice_error_to_envelope
recognize_speech = voice_input.recognize_speech
validate_audio = voice_input.validate_audio


# ---------------------------------------------------------------- #
# Fixtures                                                          #
# ---------------------------------------------------------------- #
def _make_wav_bytes(duration_sec: float = 0.2, sample_rate: int = 16000) -> bytes:
    """Generate a tiny valid WAV byte string (silent)."""
    n_samples = int(duration_sec * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def _make_mp3_bytes(size_kb: int = 8) -> bytes:
    """Generate a synthetic MP3 header + zero-padded payload.

    Real MP3 parsing is out of scope; the mock engine only inspects the
    payload length and treats this as opaque bytes.
    """
    return b"\xff\xfb" + b"\x00" * (size_kb * 1024 - 2)


@pytest.fixture
def valid_wav() -> bytes:
    return _make_wav_bytes(duration_sec=0.3)


@pytest.fixture
def valid_mp3() -> bytes:
    return _make_mp3_bytes(size_kb=8)


@pytest.fixture
def small_wav() -> bytes:
    """A valid-header WAV that's below the size minimum."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(b"\x00\x00" * 100)  # 200 bytes — below MIN
    return buf.getvalue()


# ---------------------------------------------------------------- #
# Test 1: Constants and module surface                              #
# ---------------------------------------------------------------- #
class TestConstants:
    """Verify the public constants are well-formed."""

    def test_supported_langs_count(self):
        """W14-5 spec: 4 languages (zh-CN / en / id / vi)."""
        assert len(SUPPORTED_LANGS) == 4

    def test_supported_langs_contents(self):
        """The 4 expected language codes must be present."""
        for code in ("zh-CN", "en", "id", "vi"):
            assert code in SUPPORTED_LANGS

    def test_lang_label_for_every_lang(self):
        """Every supported lang has a human-readable label."""
        for code in SUPPORTED_LANGS:
            assert code in LANG_LABEL
            assert LANG_LABEL[code]  # non-empty

    def test_size_limits_sane(self):
        """MIN < MAX and both are positive."""
        assert MIN_AUDIO_BYTES > 0
        assert MAX_AUDIO_BYTES > MIN_AUDIO_BYTES
        assert MAX_AUDIO_BYTES <= 50 * 1024 * 1024  # sanity cap

    def test_accepted_mime_types_nonempty(self):
        """At least 4 accepted mime types (WAV, MP3, OGG, FLAC...)."""
        assert len(ACCEPTED_MIME_TYPES) >= 4

    def test_timeout_positive(self):
        """RECOGNIZE_TIMEOUT_SEC must be positive and reasonable."""
        assert RECOGNIZE_TIMEOUT_SEC > 0
        assert RECOGNIZE_TIMEOUT_SEC <= 30  # not absurd


# ---------------------------------------------------------------- #
# Test 2: Audio format validation                                   #
# ---------------------------------------------------------------- #
class TestAudioFormatValidation:
    """validate_audio() rejects bad payloads, accepts good ones."""

    def test_valid_wav_accepted(self, valid_wav: bytes):
        mime = validate_audio(valid_wav)
        assert mime == "audio/wav"

    def test_valid_mp3_accepted(self, valid_mp3: bytes):
        mime = validate_audio(valid_mp3)
        assert mime == "audio/mpeg"

    def test_empty_bytes_rejected(self):
        with pytest.raises(VoiceAudioFormatError):
            validate_audio(b"")

    def test_none_rejected(self):
        with pytest.raises(VoiceAudioFormatError):
            validate_audio(None)  # type: ignore[arg-type]

    def test_wrong_type_rejected(self):
        with pytest.raises(VoiceAudioFormatError):
            validate_audio("not bytes")  # type: ignore[arg-type]

    def test_too_small_rejected(self, small_wav: bytes):
        with pytest.raises(VoiceAudioFormatError) as exc:
            validate_audio(small_wav)
        assert "too small" in str(exc.value)

    def test_too_large_rejected(self):
        # Synthetic 6 MB payload
        big = b"\x00" * (MAX_AUDIO_BYTES + 1)
        with pytest.raises(VoiceAudioFormatError) as exc:
            validate_audio(big)
        assert "too large" in str(exc.value)

    def test_unknown_signature_returns_octet_stream(self):
        # Random bytes, valid size, no recognisable signature
        rand = b"\x42\x42\x42" + b"\x00" * (MIN_AUDIO_BYTES - 3)
        mime = validate_audio(rand)
        assert mime == "application/octet-stream"


# ---------------------------------------------------------------- #
# Test 3: Language validation                                       #
# ---------------------------------------------------------------- #
class TestLanguageValidation:
    """Unsupported languages must be rejected up-front."""

    def test_unsupported_lang_raises_format_error(self):
        with pytest.raises(VoiceAudioFormatError) as exc:
            recognize_speech(_make_wav_bytes(0.3), lang="fr")
        assert "Unsupported language" in str(exc.value)

    def test_empty_lang_raises_format_error(self):
        with pytest.raises(VoiceAudioFormatError):
            recognize_speech(_make_wav_bytes(0.3), lang="")

    def test_non_string_lang_raises_format_error(self):
        with pytest.raises(VoiceAudioFormatError):
            recognize_speech(_make_wav_bytes(0.3), lang=None)  # type: ignore[arg-type]

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_each_supported_lang_passes_validation(self, lang: str):
        # Should not raise
        result = recognize_speech(_make_wav_bytes(0.3), lang=lang)
        assert result["lang"] == lang


# ---------------------------------------------------------------- #
# Test 4: recognize_speech — Chinese                                #
# ---------------------------------------------------------------- #
class TestRecognizeSpeechChinese:
    """Chinese transcript must surface name / address / travel_date."""

    def test_returns_structured_fields(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="zh-CN")
        # Shape contract
        for key in ("name", "address", "travel_date", "raw_text",
                    "lang", "confidence", "engine"):
            assert key in result, f"missing key {key}"
        assert result["lang"] == "zh-CN"
        assert result["engine"] == "mock"

    def test_extracts_chinese_name(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="zh-CN")
        # Mock transcript contains one of: 张三/李四/王五/赵六
        assert result["name"] in {"张三", "李四", "王五", "赵六"}

    def test_extracts_chinese_travel_date(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="zh-CN")
        # ISO YYYY-MM-DD
        assert result["travel_date"] is not None
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", result["travel_date"])

    def test_extracts_chinese_address(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="zh-CN")
        # Address is non-empty Chinese text
        assert result["address"] is not None
        assert len(result["address"]) >= 4

    def test_raw_text_is_nonempty(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="zh-CN")
        assert isinstance(result["raw_text"], str)
        assert len(result["raw_text"]) > 0


# ---------------------------------------------------------------- #
# Test 5: recognize_speech — English                                #
# ---------------------------------------------------------------- #
class TestRecognizeSpeechEnglish:
    """English transcript must surface name / address / travel_date."""

    def test_returns_structured_fields(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        for key in ("name", "address", "travel_date", "raw_text",
                    "lang", "confidence", "engine"):
            assert key in result
        assert result["lang"] == "en"

    def test_extracts_english_name(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        # Mock transcript contains one of: John Smith / Sarah Johnson /
        # Michael Brown / Emily Davis
        assert result["name"] in {
            "John Smith", "Sarah Johnson", "Michael Brown", "Emily Davis"
        }

    def test_extracts_english_travel_date(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        import re
        assert result["travel_date"] is not None
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", result["travel_date"])

    def test_extracts_english_address(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        assert result["address"] is not None
        assert len(result["address"]) >= 4

    def test_confidence_is_float_between_0_and_1(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------- #
# Test 6: recognize_speech — Indonesian / Vietnamese                #
# ---------------------------------------------------------------- #
class TestRecognizeSpeechIdVi:
    """Indonesian + Vietnamese paths use the same pipeline."""

    def test_indonesian_extracts_name(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="id")
        assert result["name"] in {"Andi", "Budi", "Citra", "Dewi"}
        assert result["travel_date"] is not None

    def test_vietnamese_extracts_name(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="vi")
        # Trần Thị B contains a space; the regex captures the full
        # multi-word name.
        assert result["name"] is not None
        assert result["name"].startswith(("Nguyễn", "Trần", "Lê", "Phạm"))
        assert result["travel_date"] is not None


# ---------------------------------------------------------------- #
# Test 7: Invalid audio format                                      #
# ---------------------------------------------------------------- #
class TestRecognizeInvalidAudioFormat:
    """Audio that fails validation must surface a structured error."""

    def test_empty_audio_raises_format_error(self):
        with pytest.raises(VoiceAudioFormatError) as exc:
            recognize_speech(b"", lang="en")
        assert exc.value.code == "VOICE_AUDIO_FORMAT"

    def test_oversized_audio_raises_format_error(self):
        big = b"\x00" * (MAX_AUDIO_BYTES + 1)
        with pytest.raises(VoiceAudioFormatError):
            recognize_speech(big, lang="en")

    def test_truncated_audio_raises_format_error(self):
        # Random bytes that are too small
        with pytest.raises(VoiceAudioFormatError):
            recognize_speech(b"\x00\x01\x02", lang="en")

    def test_error_envelope_uses_code_2003(self):
        try:
            recognize_speech(b"", lang="en")
        except VoiceInputError as exc:
            env = map_voice_error_to_envelope(exc)
            assert env["code"] == "2003"
            assert env["http_status"] == 400
            assert env["data"]["error_code"] == "VOICE_AUDIO_FORMAT"


# ---------------------------------------------------------------- #
# Test 8: Timeout                                                   #
# ---------------------------------------------------------------- #
class TestRecognizeTimeout:
    """Engine exceeding timeout_sec must raise VoiceTimeoutError."""

    def test_explicit_short_timeout_via_slow_engine(self, valid_wav: bytes):
        """Patch the engine to sleep longer than the timeout."""
        from app_services_voice_input import RecognitionResult

        def _slow_engine(audio_bytes, lang, timeout_sec):
            # Sleep longer than the timeout to trigger the wall-clock check.
            time.sleep(0.2)
            return RecognitionResult(
                transcript="ok", confidence=0.5, engine="slow"
            )

        voice_input._ENGINES["mock"] = _slow_engine
        try:
            with pytest.raises(VoiceTimeoutError) as exc:
                recognize_speech(valid_wav, lang="en", timeout_sec=0.05)
            assert exc.value.code == "VOICE_TIMEOUT"
            assert "exceeded" in exc.value.message
        finally:
            # Restore the original mock engine so other tests aren't affected.
            voice_input._ENGINES["mock"] = voice_input._mock_engine

    def test_timeout_envelope_uses_code_2005(self):
        exc = VoiceTimeoutError("synthetic timeout")
        env = map_voice_error_to_envelope(exc)
        assert env["code"] == "2005"
        assert env["http_status"] == 504
        assert env["data"]["error_code"] == "VOICE_TIMEOUT"


# ---------------------------------------------------------------- #
# Test 9: extract_fields() heuristic                                #
# ---------------------------------------------------------------- #
class TestExtractFieldsHeuristic:
    """Direct unit tests of the field-extraction regex set."""

    def test_chinese_extracts_name_and_date(self):
        text = "我叫张三,2026年8月15日出发,地址是上海市浦东新区世纪大道100号"
        fields = extract_fields(text, lang="zh-CN")
        assert fields["name"] == "张三"
        assert fields["travel_date"] is not None
        assert fields["address"] is not None
        assert "上海" in fields["address"] or "世纪" in fields["address"]

    def test_english_extracts_name_and_date(self):
        text = "My name is John Smith, travel date 2026-08-15, I live at 100 Main Street"
        fields = extract_fields(text, lang="en")
        assert fields["name"] == "John Smith"
        assert fields["travel_date"] == "2026-08-15"
        assert "Main Street" in fields["address"]

    def test_id_extracts_name(self):
        text = "Nama saya Andi, tinggal di Jalan Sudirman 100, tanggal 2026-08-15"
        fields = extract_fields(text, lang="id")
        assert fields["name"] == "Andi"
        assert fields["travel_date"] == "2026-08-15"

    def test_vi_extracts_name(self):
        text = "Tên tôi là Nguyễn Văn A, ngày khởi hành 2026-08-15"
        fields = extract_fields(text, lang="vi")
        assert fields["name"] == "Nguyễn Văn A"
        assert fields["travel_date"] == "2026-08-15"

    def test_no_match_returns_none_for_fields(self):
        text = "Hello world, no useful fields here"
        fields = extract_fields(text, lang="en")
        # Name / address / travel_date all None
        assert fields["name"] is None
        assert fields["address"] is None
        assert fields["travel_date"] is None
        # raw_text always passthrough
        assert fields["raw_text"] == text
        assert fields["lang"] == "en"

    def test_keys_always_present(self):
        """extract_fields must return every well-known key, even when None."""
        text = "noise"
        fields = extract_fields(text, lang="zh-CN")
        for k in ("name", "address", "travel_date", "raw_text", "lang"):
            assert k in fields


# ---------------------------------------------------------------- #
# Test 10: map_voice_error_to_envelope                              #
# ---------------------------------------------------------------- #
class TestMapVoiceErrorToEnvelope:
    """Error mapping is stable across the API surface."""

    def test_format_error_maps_to_2003(self):
        env = map_voice_error_to_envelope(VoiceAudioFormatError("bad"))
        assert env["code"] == "2003"
        assert env["http_status"] == 400

    def test_recognize_error_maps_to_2004(self):
        env = map_voice_error_to_envelope(VoiceRecognizeError("nope"))
        assert env["code"] == "2004"
        assert env["http_status"] == 422

    def test_timeout_error_maps_to_2005(self):
        env = map_voice_error_to_envelope(VoiceTimeoutError("slow"))
        assert env["code"] == "2005"
        assert env["http_status"] == 504

    def test_unknown_code_defaults_to_2003(self):
        env = map_voice_error_to_envelope(VoiceInputError("WEIRD_CODE", "x"))
        assert env["code"] == "2003"
        assert env["http_status"] == 400


# ---------------------------------------------------------------- #
# Test 11: Recognise via different audio formats (parity)           #
# ---------------------------------------------------------------- #
class TestRecognizeSpeechFormatParity:
    """The same ASR call works for WAV and MP3 inputs."""

    def test_wav_works(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        assert "name" in result

    def test_mp3_works(self, valid_mp3: bytes):
        result = recognize_speech(valid_mp3, lang="en")
        assert "name" in result

    def test_elapsed_ms_recorded(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        assert "elapsed_ms" in result
        assert isinstance(result["elapsed_ms"], int)
        assert result["elapsed_ms"] >= 0

    def test_audio_bytes_recorded(self, valid_wav: bytes):
        result = recognize_speech(valid_wav, lang="en")
        assert result["audio_bytes"] == len(valid_wav)
