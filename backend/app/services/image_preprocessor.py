"""ImagePreprocessor — 扫描文档自动剪裁与增强 (V2 §4.3.3 增强).

Pipeline:
  1. 读取图片 → 灰度
  2. 自适应高斯模糊去噪
  3. Canny 边缘检测
  4. 找最大四边形轮廓 (≈ 文档边界)
  5. 透视变换得到"对齐"后的图
  6. 自适应二值化增强对比度 (可选)
  7. 输出标准化 JPEG + 元数据

设计目标: 处理用户随手拍的护照/身份证/银行流水照片 → 转成 A4 比例、
端正、黑底白字的扫描件,像 Adobe Scan / CamScanner 的效果.

环境要求: opencv-python-headless + pillow + numpy (均在 requirements.txt).
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2  # opencv-python-headless
import numpy as np
from PIL import Image, ImageOps


# ---------------------------------------------------------------- #
# Result types                                                       #
# ---------------------------------------------------------------- #
@dataclass
class PreprocessResult:
    """Output of :meth:`ImagePreprocessor.preprocess`."""

    # processed image bytes (JPEG quality 92)
    image_bytes: bytes
    # width × height after perspective correction
    width: int
    height: int
    # MIME (always image/jpeg after we encode)
    mime_type: str = "image/jpeg"
    # output JPEG size in bytes
    size_bytes: int = 0
    # detected 4 corners in original image coords (TL, TR, BR, BL) — None if no doc found
    corners: Optional[List[List[int]]] = None
    # confidence score 0.0–1.0 — heuristic combining area, angle, edge density
    confidence: float = 0.0
    # whether we actually did perspective correction (False = passthrough)
    corrected: bool = False
    # pipeline stages actually executed (for telemetry / debug)
    stages: List[str] = field(default_factory=list)
    # warnings (non-fatal: e.g. "image too small, returned as-is")
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------- #
# Preprocessor                                                       #
# ---------------------------------------------------------------- #
class ImagePreprocessor:
    """Document scan-style preprocessing for material uploads."""

    # minimum input dimension to bother running the full pipeline
    MIN_DIM = 240
    # target longer edge after perspective correction (2400 ~= A4 300dpi short side)
    TARGET_LONG_EDGE = 1800
    # Canny thresholds — empirically work for ID/passport photos
    CANNY_LOW = 50
    CANNY_HIGH = 150
    # min area ratio (largest contour / image area) for "this is a document" decision
    MIN_AREA_RATIO = 0.20

    # ------------------------------------------------------------------ #
    # public API                                                          #
    # ------------------------------------------------------------------ #
    def preprocess(
        self,
        data: bytes,
        *,
        force_grayscale: bool = False,
        apply_binarize: bool = False,
    ) -> PreprocessResult:
        """Run the full pipeline. Returns the processed image + diagnostics.

        On any failure inside the pipeline (decode error, no contour, etc.)
        we fall back to the original image bytes so the upload never breaks.
        """
        stages: List[str] = []
        warnings: List[str] = []

        try:
            img_bgr = self._decode(data)
        except Exception as exc:
            warnings.append(f"decode_failed: {exc}")
            return self._passthrough(data, warnings=warnings, stages=["decode_failed"])

        stages.append("decoded")
        h, w = img_bgr.shape[:2]

        # tiny image — too small to detect edges reliably, just return original
        if min(h, w) < self.MIN_DIM:
            warnings.append(f"image_too_small({w}x{h})")
            return self._passthrough(
                data, width=w, height=h, warnings=warnings, stages=stages + ["passthrough_small"]
            )

        # try to detect a 4-corner document contour
        quad, conf = self._detect_document_quad(img_bgr)
        stages.append("edge_detect")

        if quad is None:
            warnings.append("no_document_quad_detected")
            return self._passthrough(
                data, width=w, height=h, confidence=conf,
                warnings=warnings, stages=stages + ["passthrough_no_quad"],
            )

        # perspective correction
        warped = self._four_point_transform(img_bgr, quad)
        stages.append("perspective_corrected")

        if apply_binarize:
            warped = self._adaptive_binarize(warped)
            stages.append("binarized")
        else:
            # light contrast enhancement for color docs (passports have photos)
            warped = self._enhance_contrast(warped)
            stages.append("contrast_enhanced")

        if force_grayscale:
            warped = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
            warped = cv2.cvtColor(warped, cv2.COLOR_GRAY2BGR)
            stages.append("grayscale")

        # resize to standard long edge for predictable downstream OCR
        warped = self._resize_long_edge(warped, self.TARGET_LONG_EDGE)
        stages.append("resized")

        # encode as JPEG (lossless for storage would balloon to >5MB, JPEG q92 is plenty)
        ok, buf = cv2.imencode(".jpg", warped, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            warnings.append("encode_failed")
            return self._passthrough(data, warnings=warnings, stages=stages + ["encode_failed"])

        out_bytes = buf.tobytes()
        out_h, out_w = warped.shape[:2]

        return PreprocessResult(
            image_bytes=out_bytes,
            width=out_w,
            height=out_h,
            size_bytes=len(out_bytes),
            corners=[[int(p[0]), int(p[1])] for p in quad],
            confidence=round(conf, 3),
            corrected=True,
            stages=stages,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #
    # pipeline steps                                                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _decode(data: bytes) -> np.ndarray:
        """Decode bytes → BGR ndarray. Raises on bad data."""
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            # last resort — try PIL (handles some HEIC / weird JPEG variants)
            pil = Image.open(io.BytesIO(data)).convert("RGB")
            img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if img is None:
            raise ValueError("could not decode image")
        return img

    def _detect_document_quad(
        self, img_bgr: np.ndarray
    ) -> Tuple[Optional[np.ndarray], float]:
        """Find the largest 4-vertex contour. Returns (quad, confidence) or (None, 0).

        Confidence heuristic:
          confidence = area_ratio * 0.6 + angle_score * 0.4
        where area_ratio = contour_area / image_area, angle_score = how close the
        4 inner angles are to 90° (1.0 if all within ±5°, drops to 0 if any > 30°).
        """
        h, w = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, self.CANNY_LOW, self.CANNY_HIGH)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        image_area = float(h * w)

        for cnt in contours[:5]:
            area = cv2.contourArea(cnt)
            if area / image_area < self.MIN_AREA_RATIO:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                quad = approx.reshape(4, 2).astype(np.float32)
                # check the quad is "fully inside" the image (not the edge)
                if np.any(quad[:, 0] < 0) or np.any(quad[:, 0] >= w) or \
                   np.any(quad[:, 1] < 0) or np.any(quad[:, 1] >= h):
                    continue
                area_ratio = area / image_area
                angle_score = self._quad_angle_score(quad)
                confidence = area_ratio * 0.6 + angle_score * 0.4
                # ensure the quad is convex
                if not cv2.isContourConvex(approx):
                    continue
                return quad, confidence
        return None, 0.0

    @staticmethod
    def _quad_angle_score(quad: np.ndarray) -> float:
        """1.0 = all 4 corners within 5° of 90°. 0.0 = any corner > 30° off."""
        scores: List[float] = []
        for i in range(4):
            p0 = quad[(i - 1) % 4]
            p1 = quad[i]
            p2 = quad[(i + 1) % 4]
            v0 = p0 - p1
            v1 = p2 - p1
            angle = math.degrees(
                math.acos(
                    max(
                        -1.0,
                        min(
                            1.0,
                            float(np.dot(v0, v1))
                            / (np.linalg.norm(v0) * np.linalg.norm(v1) + 1e-9),
                        ),
                    )
                )
            )
            dev = abs(angle - 90.0)
            if dev > 30:
                return 0.0
            scores.append(max(0.0, 1.0 - dev / 30.0))
        return sum(scores) / len(scores)

    @staticmethod
    def _order_points(pts: np.ndarray) -> np.ndarray:
        """Return (TL, TR, BR, BL)."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        rect[0] = pts[np.argmin(s)]      # TL: smallest x+y
        rect[2] = pts[np.argmax(s)]      # BR: largest x+y
        rect[1] = pts[np.argmin(diff)]   # TR: smallest x-y (y up in screen coords)
        rect[3] = pts[np.argmax(diff)]   # BL: largest x-y
        return rect

    def _four_point_transform(
        self, img_bgr: np.ndarray, quad: np.ndarray
    ) -> np.ndarray:
        """Apply perspective warp to a 4-corner document quad."""
        rect = self._order_points(quad.astype(np.float32))
        (tl, tr, br, bl) = rect

        # compute target width = max of two horizontal edge lengths
        width_a = np.linalg.norm(br - bl)
        width_b = np.linalg.norm(tr - tl)
        max_w = int(max(width_a, width_b))

        # target height = max of two vertical edge lengths
        height_a = np.linalg.norm(tr - br)
        height_b = np.linalg.norm(tl - bl)
        max_h = int(max(height_a, height_b))

        dst = np.array(
            [[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]],
            dtype=np.float32,
        )
        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(img_bgr, M, (max_w, max_h))

    @staticmethod
    def _adaptive_binarize(img_bgr: np.ndarray) -> np.ndarray:
        """Adaptive Gaussian thresholding — great for receipts, bank statements."""
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        bw = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 21, 10,
        )
        return cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def _enhance_contrast(img_bgr: np.ndarray) -> np.ndarray:
        """Mild CLAHE on L channel — keeps color but cleans shadows."""
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _resize_long_edge(img_bgr: np.ndarray, target: int) -> np.ndarray:
        h, w = img_bgr.shape[:2]
        long_edge = max(h, w)
        if long_edge <= target:
            return img_bgr
        scale = target / long_edge
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # ------------------------------------------------------------------ #
    # passthrough — never break the upload                                #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _passthrough(
        data: bytes,
        *,
        width: int = 0,
        height: int = 0,
        confidence: float = 0.0,
        warnings: Optional[List[str]] = None,
        stages: Optional[List[str]] = None,
    ) -> PreprocessResult:
        return PreprocessResult(
            image_bytes=data,
            width=width,
            height=height,
            size_bytes=len(data),
            corners=None,
            confidence=confidence,
            corrected=False,
            stages=stages or [],
            warnings=warnings or [],
        )


# ---------------------------------------------------------------- #
# Convenience singleton                                              #
# ---------------------------------------------------------------- #
_default_preprocessor: Optional[ImagePreprocessor] = None


def get_preprocessor() -> ImagePreprocessor:
    global _default_preprocessor
    if _default_preprocessor is None:
        _default_preprocessor = ImagePreprocessor()
    return _default_preprocessor