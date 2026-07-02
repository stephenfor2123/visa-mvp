"""ImagePreprocessor — 清晰度 (blur) + 完整度 (edge-cutoff) regression tests.

Previously `app/services/image_preprocessor.py` had zero test coverage.
These tests synthesize documents with cv2 so blur/margin are precisely
controlled (real photos are too noisy to assert exact thresholds against).
"""
from __future__ import annotations

import pytest

# cv2 (opencv-python) is a heavy optional dep; skip the module if missing,
# same convention as tests/integration/test_ocr_end_to_end.py.
pytest.importorskip("cv2", reason="opencv-python not installed; skip preprocessor tests")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app.services.image_preprocessor import ImagePreprocessor  # noqa: E402


def _make_document_image(w: int, h: int, margin: int, *, texture: bool = True) -> np.ndarray:
    """White rectangle (the "document") on a dark background, with
    optional black grid-lines/text so it has real Laplacian-detectable
    texture (a flat white rectangle alone has near-zero variance)."""
    img = np.full((h, w, 3), 40, dtype=np.uint8)
    cv2.rectangle(img, (margin, margin), (w - margin, h - margin), (255, 255, 255), -1)
    if texture:
        for y in range(margin + 20, h - margin - 20, 24):
            cv2.line(img, (margin + 10, y), (w - margin - 10, y), (0, 0, 0), 2)
        for x in range(margin + 20, w - margin - 20, 120):
            cv2.putText(
                img, "TEXT", (x, margin + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1
            )
    return img


def _encode_jpg(img_bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", img_bgr)
    assert ok
    return buf.tobytes()


@pytest.fixture()
def preprocessor() -> ImagePreprocessor:
    return ImagePreprocessor()


# --------------------------------------------------------------------------- #
# 清晰度 (blur detection)                                                     #
# --------------------------------------------------------------------------- #
class TestBlurDetection:
    def test_blur_score_sharp_higher_than_blurry(self, preprocessor):
        sharp = _make_document_image(800, 600, 100)
        blurry = cv2.GaussianBlur(sharp, (31, 31), 0)
        assert preprocessor._blur_score(sharp) > preprocessor._blur_score(blurry)

    def test_sharp_document_not_flagged_blurry(self, preprocessor):
        data = _encode_jpg(_make_document_image(800, 600, 100))
        result = preprocessor.preprocess(data)
        assert result.is_blurry is False
        assert result.blur_score > preprocessor.BLUR_VARIANCE_THRESHOLD
        assert not any("blurry" in w for w in result.warnings)

    def test_blurry_document_flagged_with_warning(self, preprocessor):
        sharp = _make_document_image(800, 600, 100)
        blurry = cv2.GaussianBlur(sharp, (31, 31), 0)
        result = preprocessor.preprocess(_encode_jpg(blurry))
        assert result.is_blurry is True
        assert result.blur_score < preprocessor.BLUR_VARIANCE_THRESHOLD
        assert any("blurry" in w for w in result.warnings)

    def test_tiny_image_skips_blur_check(self, preprocessor):
        # below MIN_DIM — passthrough path never measures blur
        tiny = np.full((100, 100, 3), 200, dtype=np.uint8)
        result = preprocessor.preprocess(_encode_jpg(tiny))
        assert result.corrected is False
        assert result.blur_score == 0.0
        assert result.is_blurry is False


# --------------------------------------------------------------------------- #
# 完整度 (document edge-cutoff / completeness)                                #
# --------------------------------------------------------------------------- #
class TestCompletenessDetection:
    def test_document_with_healthy_margin_is_complete(self, preprocessor):
        data = _encode_jpg(_make_document_image(800, 600, 100))
        result = preprocessor.preprocess(data)
        assert result.corrected is True
        assert result.is_complete is True
        assert "document_edge_may_be_cut_off" not in result.warnings

    def test_document_touching_frame_edge_is_incomplete(self, preprocessor):
        # margin=5 on a 1200x1000 canvas sits inside the 1% cutoff band
        # (max(2, 1000*0.01) = 10px) on all four corners.
        data = _encode_jpg(_make_document_image(1200, 1000, 5))
        result = preprocessor.preprocess(data)
        assert result.corrected is True
        assert result.is_complete is False
        assert "document_edge_may_be_cut_off" in result.warnings

    def test_document_just_outside_cutoff_band_is_complete(self, preprocessor):
        # margin=15 clears the 10px cutoff band on a 1200x1000 canvas.
        data = _encode_jpg(_make_document_image(1200, 1000, 15))
        result = preprocessor.preprocess(data)
        assert result.is_complete is True
        assert "document_edge_may_be_cut_off" not in result.warnings

    def test_is_quad_complete_direct(self, preprocessor):
        w, h = 1000, 800
        # all corners comfortably inside
        good_quad = np.array([[50, 50], [950, 50], [950, 750], [50, 750]], dtype=np.float32)
        assert preprocessor._is_quad_complete(good_quad, w, h) is True

        # two corners sitting on the left edge (x=0)
        bad_quad = np.array([[0, 0], [950, 50], [950, 750], [0, 750]], dtype=np.float32)
        assert preprocessor._is_quad_complete(bad_quad, w, h) is False

    def test_no_quad_detected_leaves_completeness_unknown_true(self, preprocessor):
        # smooth gradient — no edges for Canny to find, so no quad detected
        h, w = 600, 800
        gradient = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            gradient[y, :, :] = int(255 * y / h)
        result = preprocessor.preprocess(_encode_jpg(gradient))
        assert result.corrected is False
        assert "no_document_quad_detected" in result.warnings
        assert result.is_complete is True  # default: nothing to judge against
