"""
Base Visa Provider — abstract interface for country-specific visa automation.

Each country provider implements site-specific:
  - Form URL discovery
  - Form parsing
  - Field mapping and filling
  - Submission and confirmation extraction
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import yaml

from app.core.config import BACKEND_ROOT
from app.services.rpa.captcha_solver import CaptchaSolver
from app.services.rpa.form_filler import FormFiller
from app.services.rpa.page_parser import PageParser

logger = logging.getLogger(__name__)


@dataclass
class VisaApplicationResult:
    """Result of a visa application submission."""
    success: bool
    confirmation_no: Optional[str] = None
    message: str = ""
    order_ref: Optional[str] = None
    raw_response: Optional[dict] = None
    status_code: int = 0


class BaseVisaProvider(ABC):
    """
    Abstract base class for country-specific visa website automation.

    Subclass for each target country and implement:
      - get_form_url()
      - parse_form()
      - fill_form()
      - submit()

    Parameters
    ----------
    country_code : str
        ISO 3166-1 alpha-2 country code (e.g. "ID", "VN", "PH").
    mock_mode : bool
        If True, uses mock responses without real network calls.
    """

    country_code: str = ""

    def __init__(
        self,
        mock_mode: bool = True,
        config_path: Optional[str] = None,
    ) -> None:
        self._config_path = config_path or str(BACKEND_ROOT / "data" / "rpa_config.yaml")
        self._load_config()
        self._mock_mode = mock_mode or self._config.get("mock_mode", True)

        # Shared components
        self._captcha_solver = CaptchaSolver(config_path=self._config_path)
        self._page_parser = PageParser(config_path=self._config_path)
        self._form_filler = FormFiller(
            mapping_path=str(BACKEND_ROOT / "data" / "passport_field_mapping.yaml"),
            config_path=self._config_path,
        )

    def _load_config(self) -> None:
        """Load RPA config from YAML."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            self._config = {}
        except yaml.YAMLError:
            self._config = {}

    @property
    def mock_mode(self) -> bool:
        """Whether this provider operates in mock mode."""
        return self._mock_mode

    @property
    def captcha_solver(self) -> CaptchaSolver:
        """Shared captcha solver instance."""
        return self._captcha_solver

    @property
    def page_parser(self) -> PageParser:
        """Shared page parser instance."""
        return self._page_parser

    @property
    def form_filler(self) -> FormFiller:
        """Shared form filler instance."""
        return self._form_filler

    # ------------------------------------------------------------------ #
    # Abstract interface                                                 #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def get_form_url(self) -> str:
        """
        Return the URL of the visa application form page.

        Returns
        -------
        str
            The full URL to the application form.
        """
        ...

    @abstractmethod
    def parse_form(self, html: str) -> dict[str, str]:
        """
        Parse form fields from the HTML of the application page.

        Parameters
        ----------
        html : str
            HTML content of the form page.

        Returns
        -------
        dict[str, str]
            Mapping of field_name -> field_type.
        """
        ...

    @abstractmethod
    def fill_form(
        self,
        html: str,
        passport_data: dict[str, Any],
        visa_type: str,
        captcha_solution: str,
    ) -> dict[str, Any]:
        """
        Fill the form with passport data and return the submission payload.

        Parameters
        ----------
        html : str
            HTML content of the form page.
        passport_data : dict
            Passport holder data.
        visa_type : str
            Visa type within the country.
        captcha_solution : str
            Solved captcha text.

        Returns
        -------
        dict[str, Any]
            Form data ready for submission.
        """
        ...

    @abstractmethod
    def submit(
        self,
        form_data: dict[str, Any],
        submit_url: Optional[str] = None,
    ) -> VisaApplicationResult:
        """
        Submit the filled form and return the result.

        Parameters
        ----------
        form_data : dict[str, Any]
            Filled form data from fill_form().
        submit_url : Optional[str]
            Override submission URL. If None, uses the provider's default.

        Returns
        -------
        VisaApplicationResult
            Submission result with confirmation number.
        """
        ...

    # ------------------------------------------------------------------ #
    # Common helpers                                                     #
    # ------------------------------------------------------------------ #

    def get_country_config(self) -> dict[str, Any]:
        """Return the country-specific config block."""
        return self._config.get("countries", {}).get(self.country_code, {})

    def solve_form_captcha(self, html: str) -> str:
        """
        Extract captcha image from HTML, solve it, and return the text.

        Parameters
        ----------
        html : str
            HTML content containing captcha image.

        Returns
        -------
        str
            Solved captcha text.
        """
        captcha_info = self._page_parser.parse_captcha_location(html)

        if captcha_info.get("type") == "base64":
            # Decode base64 image
            import base64, io
            from PIL import Image
            data = captcha_info["image_data"].split(",", 1)
            if len(data) == 2:
                img_bytes = base64.b64decode(data[1])
                image = Image.open(io.BytesIO(img_bytes))
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                return self._captcha_solver.solve_captcha(buf.getvalue())

        image_url = captcha_info.get("image_url")
        if not image_url:
            if self._mock_mode:
                return "mock1234"
            raise ValueError("No captcha image URL found in page")

        if self._mock_mode:
            logger.info("Mock mode: returning mock captcha for %s", image_url)
            return "mock1234"

        # Fetch captcha image
        import requests
        timeout = self._config.get("timeouts", {}).get("captcha_timeout", 20)
        response = requests.get(image_url, timeout=timeout)
        response.raise_for_status()
        return self._captcha_solver.solve_captcha(response.content)

    def get_session(self) -> Any:
        """
        Return an HTTP session for this provider.

        In mock mode, returns a mock object.
        In production, returns a requests.Session with proper headers.
        """
        if self._mock_mode:
            return MockSession()

        import requests
        session = requests.Session()
        user_agent = self._config.get("session", {}).get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36"
        )
        session.headers.update({"User-Agent": user_agent})
        return session


class MockSession:
    """Mock HTTP session for development/testing."""

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}
        self.headers: dict[str, str] = {}

    def get(self, url: str, **kwargs) -> "MockResponse":
        return MockResponse(url, "GET", **kwargs)

    def post(self, url: str, **kwargs) -> "MockResponse":
        return MockResponse(url, "POST", **kwargs)

    def __enter__(self) -> "MockSession":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class MockResponse:
    """Mock HTTP response for development/testing."""

    def __init__(self, url: str, method: str, **kwargs: Any) -> None:
        self.url = url
        self.method = method
        self.status_code = 200
        self.text = f"<html><body>Mock response for {method} {url}</body></html>"
        self.content = self.text.encode("utf-8")
        self.headers: dict[str, str] = {"Content-Type": "text/html"}

    def raise_for_status(self) -> None:
        pass