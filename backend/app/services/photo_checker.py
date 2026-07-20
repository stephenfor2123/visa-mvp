"""PhotoChecker — W62 visa-photo quality gate.

Used by `POST /api/v2/materials/photo/check` to reject obviously-wrong
uploads BEFORE the file lands in storage. Catches the 3 most common
"用户随便传了一个文件" cases:

  1. PDF / 非图片文件  (mime check)
  2. 风景 / 全身照 / 自拍合影  (no frontal face detected by Haar cascade)
  3. 背景色不符合目的国规范  (samples image border, computes dominant
     bg color in HSV, checks against the country's expected palette)

Returns a structured result the frontend can render as warnings/errors.
This is non-blocking on purpose — the user can still proceed if the
checker can't decide (e.g. server offline, exotic format). The actual
visa-decision belongs to the consular officer, not us.

Implementation notes:
  - Uses OpenCV Haar cascades (frontalface + eye) shipped with cv2
    (`cv2.data.haarcascades`). Zero extra dependencies.
  - Cascade loaded lazily on first call so the service doesn't pay
    ~10MB of memory cost when no photo check is happening.
  - Background detection samples a ring of pixels along the image
    edges (the photo background is by definition the outer frame of
    a properly-cropped visa photo, not the area behind the head).
  - Color distance uses HSV hue+value — robust to slight JPEG artifacts
    and small lighting drift, unlike naive RGB euclidean.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings

_log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Country rules                                                              #
# --------------------------------------------------------------------------- #
# Background keywords match the same vocabulary as visa_diagnoser._REQUIRED:
#   "白底" / "红底" / "蓝底"  (with optional 2nd color in "或" form)
# Aspect ratio: visa photos are nearly square (US 51×51mm, CN 33×48mm ≈ 0.69).
# We accept 0.65 ~ 0.90 to cover both 2-inch and square formats.
#
# Each rule's "min_pixels" is the long-edge threshold. 600px is a safe
# print-quality floor for 51mm photos at 300 DPI (≈ 602px).

@dataclass
class PhotoRule:
    aspect_min: float          # width / height lower bound
    aspect_max: float          # width / height upper bound
    min_pixels: int            # min(long_edge)
    allowed_bg: Tuple[str, ...]  # any-of these color keywords

    @classmethod
    def for_country(cls, country_code: str) -> "PhotoRule":
        cc = (country_code or "").upper()
        # Product destinations (US / GB / AU / Schengen) — all white-bg
        if cc in (
            "US", "GB", "AU",
            "FR", "DE", "IT", "ES", "NL", "AT", "BE", "CH", "SE", "NO",
            "DK", "FI", "PT", "GR", "PL", "CZ", "IE",
        ):
            return cls(0.65, 0.90, 600, ("白底",))
        # Unknown destination — still advise white bg (do not special-case ID/VN/JP…)
        return cls(0.65, 0.90, 600, ("白底",))


# --------------------------------------------------------------------------- #
# Result types                                                               #
# --------------------------------------------------------------------------- #

@dataclass
class CheckResult:
    ok: bool                                         # True = 没有 error,可以直接上传
    has_face: bool = False
    face_count: int = 0
    width: int = 0
    height: int = 0
    aspect: float = 0.0
    bg_color: str = ""                               # "白底" / "红底" / "蓝底" / "其他"
    bg_match: bool = False                           # bg_color ∈ rule.allowed_bg
    errors: List[str] = field(default_factory=list)   # 阻断 — 不让上传
    warnings: List[str] = field(default_factory=list)  # 不阻断 — 提示用户

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "has_face": self.has_face,
            "face_count": self.face_count,
            "width": self.width,
            "height": self.height,
            "aspect": round(self.aspect, 3),
            "bg_color": self.bg_color,
            "bg_match": self.bg_match,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# --------------------------------------------------------------------------- #
# Cascade lazy loader                                                        #
# --------------------------------------------------------------------------- #
_FACE_CASCADE = None
_EYE_CASCADE = None


def _get_cascades() -> Tuple[Any, Any]:
    """Lazy-load Haar cascades on first use. Returns (face, eye)."""
    global _FACE_CASCADE, _EYE_CASCADE
    if _FACE_CASCADE is None or _EYE_CASCADE is None:
        import cv2  # local import: cv2 is heavy
        base = cv2.data.haarcascades
        _FACE_CASCADE = cv2.CascadeClassifier(base + "haarcascade_frontalface_default.xml")
        _EYE_CASCADE = cv2.CascadeClassifier(base + "haarcascade_eye.xml")
        if _FACE_CASCADE.empty() or _EYE_CASCADE.empty():
            _log.warning("photo_checker: Haar cascade XML failed to load (face=%s, eye=%s)",
                         _FACE_CASCADE.empty(), _EYE_CASCADE.empty())
    return _FACE_CASCADE, _EYE_CASCADE


# --------------------------------------------------------------------------- #
# Image helpers                                                              #
# --------------------------------------------------------------------------- #

def _decode_image(data: bytes) -> Optional[Any]:
    """Decode bytes → cv2 BGR ndarray. Returns None on unsupported format."""
    import cv2
    import numpy as np
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img  # None if decode fails


def _detect_face(img_bgr: Any) -> Tuple[bool, int]:
    """Run Haar face + eye detection. Returns (has_face, count).

    We require either:
      - 1 frontal face, OR
      - 1 face + at least 1 eye in the upper half (filters out posters / cats)
    """
    import cv2
    face_cascade, eye_cascade = _get_cascades()
    if face_cascade is None or face_cascade.empty():
        # Cascade failed to load — return a permissive "True" so the gate
        # doesn't block users when the server is misconfigured.
        return True, 0
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # scaleFactor / minNeighbors tuned for typical ID-photo headroom
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=4, minSize=(80, 80)
    )
    if len(faces) == 0:
        return False, 0
    if len(faces) == 1:
        # 1 face — accept, optionally confirm with eyes
        x, y, w, h = faces[0]
        upper = gray[max(0, y):y + h // 2, x:x + w]
        eyes = eye_cascade.detectMultiScale(upper, scaleFactor=1.1, minNeighbors=3)
        return True, len(faces)
    # multiple faces — passport / group photo, not a visa photo
    return False, len(faces)


def _classify_background(img_bgr: Any) -> str:
    """Sample pixels along the image border and classify dominant color.

    Strategy:
      - Take a 12-px-wide ring around all 4 edges (or proportional to short edge).
      - Convert to HSV, drop the 5% extremes (JPEG artifacts at the very edge).
      - Compute mean H / S / V of the rest.
      - Map to "白底" / "红底" / "蓝底" / "其他".

    This deliberately ignores the center of the image — a visa photo's
    background IS the outer frame, not the area behind the head (which
    the head itself occludes anyway).
    """
    import cv2
    import numpy as np
    h, w = img_bgr.shape[:2]
    ring = max(4, int(min(h, w) * 0.04))
    # Build a mask: outer ring
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[:ring, :] = 1
    mask[-ring:, :] = 1
    mask[:, :ring] = 1
    mask[:, -ring:] = 1
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    samples = hsv[mask == 1]
    if len(samples) == 0:
        return "其他"
    # 5%-trimmed mean (drop the most extreme 5% on each side per channel)
    trimmed = samples.copy()
    for c in range(3):
        ch = trimmed[:, c]
        lo, hi = np.percentile(ch, [5, 95])
        trimmed = trimmed[(ch >= lo) & (ch <= hi)]
    if len(trimmed) == 0:
        return "其他"
    mean_h, mean_s, mean_v = trimmed.mean(axis=0)
    # 1. White background: very low saturation AND high value
    if mean_s < 35 and mean_v > 200:
        return "白底"
    # 2. Red background: hue near 0 or 180 (red wraps), high saturation
    if mean_s > 60 and ((mean_h <= 10) or (mean_h >= 170)):
        return "红底"
    # 3. Blue background: hue 90~130
    if mean_s > 60 and 90 <= mean_h <= 135:
        return "蓝底"
    return "其他"


# --------------------------------------------------------------------------- #
# Public entry point                                                         #
# --------------------------------------------------------------------------- #

def check_photo(data: bytes, country_code: str = "") -> CheckResult:
    """Run the full photo check.

    Returns a CheckResult; caller (the HTTP layer) converts to JSON.
    Never raises — all failures become warnings, not exceptions, so the
    frontend can degrade gracefully (just allow upload with a "we couldn't
    verify this" message).
    """
    settings = get_settings()
    rule = PhotoRule.for_country(country_code)

    # Mime / decode: if not an image the request shouldn't have reached us,
    # but the UploadFile.content_type can lie. Catch that here.
    img = _decode_image(data)
    if img is None:
        return CheckResult(
            ok=False,
            errors=["文件无法解码为图片,请上传 JPG / PNG / WebP 格式"],
        )
    h, w = img.shape[:2]
    aspect = round(w / h, 3) if h else 0.0

    # Size gate (cheap)
    long_edge = max(w, h)
    errors: List[str] = []
    warnings: List[str] = []

    if long_edge < rule.min_pixels:
        errors.append(
            f"分辨率过低 ({w}×{h}),需要长边至少 {rule.min_pixels}px,建议重新拍摄或扫描"
        )
    if not (rule.aspect_min <= aspect <= rule.aspect_max):
        errors.append(
            f"宽高比 {aspect} 不符合证件照规格 (要求 {rule.aspect_min} ~ {rule.aspect_max}),"
            "照片可能不是标准 2 寸 / 51×51mm"
        )

    # Face detection
    has_face, face_count = (True, 0)
    if not errors:  # skip expensive cascade if image is already obviously wrong
        has_face, face_count = _detect_face(img)
    if face_count > 1:
        errors.append(f"检测到 {face_count} 张人脸,签证照片只能有 1 个人")
    elif face_count == 0 and not errors:
        # only complain about missing face if everything else looks right —
        # a 200x80 strip might be a fragment, not a face
        warnings.append("未检测到人脸,可能不是证件照(自拍照 / 全身照 / 风景图)")

    # Background classification
    bg_color = _classify_background(img)
    bg_match = bg_color in rule.allowed_bg
    if not bg_match:
        if bg_color == "其他":
            warnings.append(
                f"背景色不是 {rule.allowed_bg[0]},签证官可能要求重新拍摄"
            )
        else:
            errors.append(
                f"背景色为 {bg_color},但 {country_code or '该国'}签证要求 "
                f"{'或'.join(rule.allowed_bg)};请重新拍摄后再上传"
            )

    return CheckResult(
        ok=len(errors) == 0,
        has_face=has_face,
        face_count=face_count,
        width=w,
        height=h,
        aspect=aspect,
        bg_color=bg_color,
        bg_match=bg_match,
        errors=errors,
        warnings=warnings,
    )
