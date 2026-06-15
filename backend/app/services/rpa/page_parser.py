"""
Page Parser — Parse HTML from visa websites to extract form fields and captcha elements.

Usage:
    parser = PageParser()
    fields = parser.parse_form_fields(html)
    captcha_info = parser.parse_captcha_location(html)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Union

import yaml

from app.core.config import BACKEND_ROOT

logger = logging.getLogger(__name__)


@dataclass
class CaptchaInfo:
    """Captcha element information extracted from HTML."""
    captcha_type: str  # "image" | "slider" | "math" | "text"
    image_url: Optional[str] = None
    slider_url: Optional[str] = None
    target_url: Optional[str] = None
    input_name: str = "captcha"
    element_id: Optional[str] = None
    element_selector: Optional[str] = None


@dataclass
class FormField:
    """A single form field extracted from HTML."""
    name: str
    field_type: str  #Union[text, email, tel, select, radio, checkbox, hidden, password, date, number]
    label: Optional[str] = None
    required: bool = False
    options: list[str] = field(default_factory=list)  # For select/radio
    element_id: Optional[str] = None
    element_name: Optional[str] = None
    placeholder: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None


@dataclass
class FormSpec:
    """Complete form specification parsed from HTML."""
    fields: list[FormField]
    captcha: Optional[CaptchaInfo] = None
    submit_url: Optional[str] = None
    submit_button_id: Optional[str] = None
    method: str = "POST"
    action_url: Optional[str] = None
    raw_html_hash: Optional[str] = None


class PageParseError(Exception):
    """Raised when HTML parsing fails."""
    pass


class PageParser:
    """
    Parse HTML pages from visa websites to extract form structure and captcha info.

    Parameters
    ----------
    config_path : str
        Path to rpa_config.yaml.
    mock_html : Optional[str]
        If provided, uses this HTML instead of fetching (development mode).
    """

    # Common input type mappings
    _INPUT_TYPE_MAP = {
        "text": "text",
        "email": "email",
        "tel": "tel",
        "number": "number",
        "password": "password",
        "date": "date",
        "datetime-local": "datetime-local",
        "url": "url",
        "search": "text",
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        mock_html: Optional[str] = None,
    ) -> None:
        self._config_path = config_path or str(BACKEND_ROOT / "data" / "rpa_config.yaml")
        self._mock_html = mock_html
        self._load_config()

    def _load_config(self) -> None:
        """Load RPA config from YAML."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("rpa_config.yaml not found, using defaults")
            self._config = {}
        except yaml.YAMLError as exc:
            logger.error("Failed to parse rpa_config.yaml: %s", exc)
            self._config = {}

    @property
    def mock_mode(self) -> bool:
        """Whether mock mode is enabled."""
        return self._config.get("mock_mode", True)

    def fetch_page(self, url: str, session_cookies: Optional[dict] = None) -> str:
        """
        Fetch a web page and return its HTML content.

        Parameters
        ----------
        url : str
            The URL to fetch.
        session_cookies : Optional[dict]
            Cookies to include with the request.

        Returns
        -------
        str
            HTML content of the page.
        """
        if self.mock_mode:
            logger.info("Mock mode: returning mock HTML for URL=%s", url)
            return self._mock_html or self._get_default_mock_html()

        import requests
        timeout = self._config.get("timeouts", {}).get("http_timeout", 30)
        headers = {
            "User-Agent": self._config.get("session", {}).get(
                "user_agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0"
            )
        }

        response = requests.get(url, headers=headers, cookies=session_cookies, timeout=timeout)
        response.raise_for_status()
        return response.text

    def parse_form_fields(self, html: str) -> dict[str, str]:
        """
        Parse HTML and extract all form fields with their types.

        Parameters
        ----------
        html : str
            HTML content of the page.

        Returns
        -------
        dict[str, str]
            Mapping of field_name -> field_type.
            e.g. {"family_name": "text", "gender": "select", "captcha": "text"}
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("BeautifulSoup4 not installed, using fallback parser")
            return self._parse_form_fields_fallback(html)

        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, str] = {}

        # Find all form elements
        for form in soup.find_all("form"):
            for inp in form.find_all(["input", "select", "textarea"]):
                name = inp.get("name") or inp.get("id", "")
                if not name:
                    continue

                # Determine field type
                input_type = inp.get("type", "text").lower()
                if inp.name == "select":
                    field_type = "select"
                elif inp.name == "textarea":
                    field_type = "text"
                else:
                    field_type = self._INPUT_TYPE_MAP.get(input_type, input_type)

                result[name] = field_type

        # Also check inputs outside forms (some sites use div-based forms)
        for inp in soup.find_all(["input", "select", "textarea"]):
            name = inp.get("name") or inp.get("id", "")
            if name and name not in result:
                input_type = inp.get("type", "text").lower()
                if inp.name == "select":
                    field_type = "select"
                elif inp.name == "textarea":
                    field_type = "text"
                else:
                    field_type = self._INPUT_TYPE_MAP.get(input_type, input_type)
                result[name] = field_type

        logger.info("Parsed %d form fields from HTML", len(result))
        return result

    def parse_form_spec(self, html: str) -> FormSpec:
        """
        Parse HTML and extract a complete form specification.

        Parameters
        ----------
        html : str
            HTML content of the page.

        Returns
        -------
        FormSpec
            Structured form specification.
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("BeautifulSoup4 not installed, returning basic spec")
            basic_fields = self.parse_form_fields(html)
            return FormSpec(
                fields=[FormField(name=n, field_type=t) for n, t in basic_fields.items()]
            )

        soup = BeautifulSoup(html, "html.parser")
        fields: list[FormField] = []

        for form in soup.find_all("form"):
            action_url = form.get("action", "")
            method = form.get("method", "POST").upper()

            for inp in form.find_all(["input", "select", "textarea"]):
                field = self._parse_input_element(inp)
                if field:
                    fields.append(field)

            # Also check for submit buttons
            for btn in form.find_all(["button", "input"]):
                if btn.get("type") in ("submit", "image") or btn.name == "submit":
                    submit_id = btn.get("id") or btn.get("name", "")
                    break

        # Parse captcha info
        captcha = self.parse_captcha_location(html)

        return FormSpec(
            fields=fields,
            captcha=captcha,
            method=method if fields else "POST",
            action_url=action_url if fields else None,
        )

    def _parse_input_element(self, inp) -> Optional[FormField]:
        """Parse a single input/select/textarea element into a FormField."""
        name = inp.get("name") or inp.get("id", "")
        if not name:
            return None

        input_type = inp.get("type", "text").lower()
        element_id = inp.get("id")
        placeholder = inp.get("placeholder", "")
        required = inp.get("required") is not None or inp.get("aria-required") == "true"
        min_length = inp.get("minlength")
        max_length = inp.get("maxlength")
        pattern = inp.get("pattern")

        if inp.name == "select":
            field_type = "select"
            options = [opt.get("value", "") for opt in inp.find_all("option")]
        elif inp.name == "textarea":
            field_type = "text"
            options = []
        else:
            field_type = self._INPUT_TYPE_MAP.get(input_type, input_type)
            options = []

        # Get label
        label_elem = inp.find_next("label")
        label = label_elem.get_text(strip=True) if label_elem else None

        return FormField(
            name=name,
            field_type=field_type,
            label=label,
            required=required,
            options=options,
            element_id=element_id,
            element_name=name,
            placeholder=placeholder or None,
            min_length=int(min_length) if min_length else None,
            max_length=int(max_length) if max_length else None,
            pattern=pattern or None,
        )

    def parse_captcha_location(self, html: str) -> dict[str, any]:
        """
        Parse HTML and find captcha element information.

        Parameters
        ----------
        html : str
            HTML content of the page.

        Returns
        -------
        dict[str, any]
            Dict with keys: type (str), image_urUnion[str]tr|None), input_name (str).
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return {"type": "image", "image_url": None, "input_name": "captcha"}

        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, any] = {
            "type": "none",
            "image_url": None,
            "input_name": "captcha",
        }

        # Strategy 1: Look for img with captcha-related id/class/alt
        captcha_img = soup.find("img", id=re.compile(r"captcha[_-]?image|captcha-image|captcha-img", re.I))
        if not captcha_img:
            captcha_img = soup.find("img", class_=re.compile(r"captcha", re.I))
        if not captcha_img:
            captcha_img = soup.find("img", alt=re.compile(r"captcha", re.I))
        if not captcha_img:
            captcha_img = soup.find("img", src=re.compile(r"captcha", re.I))

        if captcha_img:
            img_src = captcha_img.get("src", "")
            if img_src.startswith("data:"):
                result["type"] = "base64"
                result["image_data"] = img_src
            else:
                result["image_url"] = img_src
            result["type"] = "image"

        # Strategy 2: Look for slider captcha
        slider_bg = soup.find(
            "div", class_=re.compile(r"slider|captcha-slider", re.I)
        ) or soup.find("img", src=re.compile(r"slider", re.I))
        if slider_bg:
            result["type"] = "slider"
            img_elem = soup.find("img", src=re.compile(r"slider", re.I))
            if img_elem:
                result["slider_url"] = img_elem.get("src")
            target_img = soup.find("img", src=re.compile(r"target|缺口", re.I))
            if target_img:
                result["target_url"] = target_img.get("src")

        # Strategy 3: Look for math captcha
        math_elem = soup.find(
            "span", class_=re.compile(r"captcha-math|math-captcha", re.I)
        ) or soup.find("div", id=re.compile(r"captcha-math", re.I))
        if math_elem:
            result["type"] = "math"
            result["math_text"] = math_elem.get_text(strip=True)

        # Find the input field for captcha
        captcha_input = (
            soup.find("input", id=re.compile(r"captcha", re.I))
            or soup.find("input", attrs={"name": re.compile(r"captcha", re.I)})
            or soup.find("input", id="captcha")
            or soup.find("input", attrs={"name": "captcha"})
            or soup.find("input", id="captcha_code")
            or soup.find("input", attrs={"name": "captcha_code"})
        )
        if captcha_input:
            result["input_name"] = captcha_input.get("name", "captcha")

        logger.debug("Captcha info: type=%s, image_url=%s", result["type"], result.get("image_url"))
        return result

    def _parse_form_fields_fallback(self, html: str) -> dict[str, str]:
        """Fallback regex-based form parser when BeautifulSoup is unavailable."""
        result: dict[str, str] = {}

        # Match <input ... name="..." type="..." ...>
        input_pattern = re.compile(
            r'<input\s+[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        for match in input_pattern.finditer(html):
            name, inp_type = match.group(1), match.group(2).lower()
            result[name] = self._INPUT_TYPE_MAP.get(inp_type, inp_type)

        # Match <select ... name="..."> ... <option value="...">
        select_pattern = re.compile(
            r'<select\s+[^>]*name=["\']([^"\']+)["\'][^>]*>',
            re.IGNORECASE,
        )
        for match in select_pattern.finditer(html):
            name = match.group(1)
            result[name] = "select"

        # Match <textarea ... name="...">
        textarea_pattern = re.compile(
            r'<textarea\s+[^>]*name=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        for match in textarea_pattern.finditer(html):
            name = match.group(1)
            result[name] = "text"

        return result

    def _get_default_mock_html(self) -> str:
        """Return a sample mock HTML for development testing."""
        return """
        <html>
        <form id="visa-form" action="/submit" method="POST">
            <input type="text" id="family_name" name="family_name" required />
            <input type="text" id="given_name" name="given_name" required />
            <select id="gender" name="gender" required>
                <option value="">-- Select --</option>
                <option value="M">Male</option>
                <option value="F">Female</option>
            </select>
            <input type="date" id="birthday" name="birthday" required />
            <input type="text" id="passport_number" name="passport_number" required />
            <input type="date" id="passport_expiry" name="passport_expiry" required />
            <input type="email" id="email" name="email" required />
            <input type="tel" id="phone" name="phone" required />
            <input type="text" id="nationality" name="nationality" />
            <input type="text" id="captcha" name="captcha" required />
            <img id="captcha-image" src="/captcha.jpg" alt="Captcha" />
            <button type="submit" id="btn-submit">Submit Visa Application</button>
        </form>
        </html>
        """