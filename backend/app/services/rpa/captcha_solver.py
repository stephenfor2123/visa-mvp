"""
Captcha Solver — OCR-based captcha recognition for visa websites.

Supports:
  - pytesseract: local OCR using Tesseract (no external API calls)
  - third_party_api: remote OCR service (requires api_url + api_key)

Usage:
    solver = CaptchaSolver()
    result = solver.solve_captcha(image_bytes)
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import yaml

from app.core.config import BACKEND_ROOT

logger = logging.getLogger(__name__)


class CaptchaEngine(str, Enum):
    PYTESSERACT = "pytesseract"
    THIRD_PARTY_API = "third_party_api"


@dataclass
class CaptchaResult:
    """Result of captcha solving."""
    text: str
    confidence: float
    engine: CaptchaEngine
    attempts: int = 1


class CaptchaSolverError(Exception):
    """Raised when captcha solving fails after all retries."""
    pass


class CaptchaSolver:
    """
    Solve image captchas using pytesseract or third-party OCR API.

    Parameters
    ----------
    config_path : Optional[str]
        Path to rpa_config.yaml. If None, uses the default config.
    max_retries : int
        Maximum consecutive failures before raising CaptchaSolverError.
        Loaded from config if not provided.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self._config_path = config_path or str(BACKEND_ROOT / "data" / "rpa_config.yaml")
        self._load_config()

        self._engine = CaptchaEngine(self._config.get("captcha", {}).get("engine", "pytesseract"))
        self._preprocess = self._config.get("captcha", {}).get("preprocess", True)
        self._min_confidence = self._config.get("captcha", {}).get("min_confidence", 0.6)
        self._api_url = self._config.get("captcha", {}).get("api_url", "")
        self._api_key = self._config.get("captcha", {}).get("api_key", "")
        self._max_retries = max_retries or self._config.get("retry", {}).get("captcha_max_retries", 3)
        self._consecutive_failures = 0

    def _load_config(self) -> None:
        """Load RPA config from YAML file."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("rpa_config.yaml not found at %s, using defaults", self._config_path)
            self._config = {}
        except yaml.YAMLError as exc:
            logger.error("Failed to parse rpa_config.yaml: %s", exc)
            self._config = {}

    @property
    def engine(self) -> CaptchaEngine:
        """Current OCR engine."""
        return self._engine

    @property
    def consecutive_failures(self) -> int:
        """Number of consecutive captcha solving failures."""
        return self._consecutive_failures

    def solve_captcha(self, image_bytes: bytes) -> str:
        """
        Solve an image captcha and return the recognized text.

        Parameters
        ----------
        image_bytes : bytes
            Raw image data (PNG/JPEG/etc.) of the captcha.

        Returns
        -------
        str
            Recognized captcha text (stripped, lowercase by default).

        Raises
        ------
        CaptchaSolverError
            After ``max_retries`` consecutive failures.
        """
        if self._consecutive_failures >= self._max_retries:
            raise CaptchaSolverError(
                f"Captcha solver blocked: {self._consecutive_failures} consecutive failures "
                f"(max_retries={self._max_retries}). Manual intervention required."
            )

        try:
            if self._engine == CaptchaEngine.PYTESSERACT:
                text = self._solve_with_tesseract(image_bytes)
            elif self._engine == CaptchaEngine.THIRD_PARTY_API:
                text = self._solve_with_api(image_bytes)
            else:
                raise CaptchaSolverError(f"Unknown captcha engine: {self._engine}")

            # Normalize result
            text = text.strip().lower()

            if not text:
                self._consecutive_failures += 1
                logger.warning(
                    "Captcha solver returned empty result (attempt %d/%d)",
                    self._consecutive_failures, self._max_retries
                )
                if self._consecutive_failures >= self._max_retries:
                    raise CaptchaSolverError(
                        f"Captcha solver blocked after {self._consecutive_failures} empty results."
                    )
                return ""

            self._consecutive_failures = 0
            logger.info("Captcha solved: '%s' (engine=%s)", text, self._engine.value)
            return text

        except CaptchaSolverError:
            raise
        except Exception as exc:
            self._consecutive_failures += 1
            logger.error(
                "Captcha solve error: %s (attempt %d/%d)",
                exc, self._consecutive_failures, self._max_retries
            )
            if self._consecutive_failures >= self._max_retries:
                raise CaptchaSolverError(
                    f"Captcha solver failed after {self._consecutive_failures} attempts: {exc}"
                )
            raise

    def _solve_with_tesseract(self, image_bytes: bytes) -> str:
        """
        Solve captcha using pytesseract (local OCR).

        Parameters
        ----------
        image_bytes : bytes
            Raw image data.

        Returns
        -------
        str
            Recognized text.
        """
        try:
            from PIL import Image
        except ImportError:
            # Fallback: return mock text in dev/mock mode
            logger.warning("PIL/Pillow not installed, returning mock captcha text")
            return "mock1234"

        image = Image.open(io.BytesIO(image_bytes))

        if self._preprocess:
            from PIL import ImageFilter, ImageEnhance
            # Convert to grayscale
            image = image.convert("L")
            # Increase contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            # Sharpen
            image = image.filter(ImageFilter.SHARPEN)

        import pytesseract
        result = pytesseract.image_to_string(image, config="--psm 7")
        return result.strip()

    def _solve_with_api(self, image_bytes: bytes) -> str:
        """
        Solve captcha using a third-party OCR API.

        Parameters
        ----------
        image_bytes : bytes
            Raw image data.

        Returns
        -------
        str
            Recognized text.
        """
        if not self._api_url:
            raise CaptchaSolverError(
                "Third-party API URL not configured. Set captcha.api_url in rpa_config.yaml"
            )

        import requests

        files = {"image": ("captcha.png", image_bytes, "image/png")}
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        response = requests.post(
            self._api_url,
            files=files,
            headers=headers,
            timeout=self._config.get("timeouts", {}).get("captcha_timeout", 20),
        )
        response.raise_for_status()

        data = response.json()
        text = data.get("text", "") or data.get("result", "") or data.get("data", "")

        if isinstance(text, dict):
            text = text.get("text", "")

        return str(text).strip()

    def solve_slider_captcha(
        self,
        slider_url: str,
        target_url: str,
        slider_distance: float,
    ) -> dict:
        """
        Solve a slider (drag-to-complete) captcha.

        Parameters
        ----------
        slider_url : str
            URL of the slider background image.
        target_url : str
            URL of the target position indicator image.
        slider_distance : float
            The distance to drag (0.0 to 1.0, normalized).

        Returns
        -------
        dict
            Result containing 'track' (list of x,y steps) and 'distance'.
            In mock mode, returns a simulated track.
        """
        # Mock implementation for development
        logger.info(
            "Slider captcha: slider_url=%s, distance=%.2f",
            slider_url, slider_distance
        )
        # Simulate a human-like drag track
        steps = int(slider_distance * 300)
        track = []
        current = 0
        while current < steps:
            current += 5
            track.append((current, 0))
        return {
            "track": track,
            "distance": slider_distance,
            "engine": self._engine.value,
            "mock": True,
        }

    def reset_failures(self) -> None:
        """Reset consecutive failure counter after successful solve."""
        self._consecutive_failures = 0
        logger.debug("Captcha solver failure counter reset")