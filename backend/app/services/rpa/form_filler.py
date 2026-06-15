"""
Form Filler — Map passport data to visa website form fields and submit.

Usage:
    filler = FormFiller()
    mapped = filler.map_fields(passport_data, "ID")
    result = filler.submit_form(session, mapped)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional, Union

import yaml

from app.core.config import BACKEND_ROOT

logger = logging.getLogger(__name__)


@dataclass
class FormSubmitResult:
    """Result of a form submission."""
    success: bool
    message: str
    order_ref: Optional[str] = None
    confirmation_no: Optional[str] = None
    raw_response: Optional[dict] = None
    status_code: int = 0


class FormFillerError(Exception):
    """Raised when form filling or submission fails."""
    pass


class FormFiller:
    """
    Map passport data to visa website form fields and submit the form.

    Parameters
    ----------
    mapping_path : Optional[str]
        Path to passport_field_mapping.yaml.
    config_path : Optional[str]
        Path to rpa_config.yaml.
    """

    def __init__(
        self,
        mapping_path: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> None:
        self._mapping_path = mapping_path or str(BACKEND_ROOT / "data" / "passport_field_mapping.yaml")
        self._config_path = config_path or str(BACKEND_ROOT / "data" / "rpa_config.yaml")
        self._load_mapping()
        self._load_config()

    def _load_mapping(self) -> None:
        """Load passport field mapping from YAML."""
        try:
            with open(self._mapping_path, "r", encoding="utf-8") as f:
                self._mapping = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("passport_field_mapping.yaml not found at %s", self._mapping_path)
            self._mapping = {"countries": {}}
        except yaml.YAMLError as exc:
            logger.error("Failed to parse passport_field_mapping.yaml: %s", exc)
            self._mapping = {"countries": {}}

    def _load_config(self) -> None:
        """Load RPA config from YAML."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            self._config = {}
        except yaml.YAMLError as exc:
            logger.error("Failed to parse rpa_config.yaml: %s", exc)
            self._config = {}

    @property
    def mock_mode(self) -> bool:
        """Whether mock mode is enabled."""
        return self._config.get("mock_mode", True)

    def _countries(self) -> dict:
        """Return the countries dict (handles both flat and nested YAML structures)."""
        if "countries" in self._mapping:
            return self._mapping["countries"]
        # Flat structure: top-level keys ARE country codes
        return {k: v for k, v in self._mapping.items()
                if k not in ("date_formats", "gender_map", "required_fields")}

    def get_supported_countries(self) -> list[str]:
        """Return list of supported country codes (uppercase)."""
        return [k.upper() for k in self._countries().keys()]

    def get_visa_types(self, country_code: str) -> list[str]:
        """Return available visa types for a country."""
        code = country_code.upper()
        countries = self._countries()
        country_data = countries.get(code) or countries.get(code.lower()) or {}
        return list(country_data.get("visa_types", {}).keys())

    def get_required_fields(self, country_code: str, visa_type: str) -> list[str]:
        """Return required fields for a country + visa type combination."""
        return self._mapping.get("required_fields", {}).get(country_code.upper(), [])

    def map_fields(
        self,
        passport_data: dict[str, Any],
        country_code: str,
        visa_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Map passport data fields to visa website form fields.

        Parameters
        ----------
        passport_data : dict
            Passport holder data. Expected keys: surname, given_name,
            date_of_birth, passport_no, passport_expiry, nationality, sex,
            email, phone (and optional: travel_date, port_of_boarding, flight_no).
        country_code : str
            ISO 3166-1 alpha-2 country code (e.g. "ID", "VN", "PH").
        visa_ty : Optional[str] = None
            Visa type within the country. If None, uses the first available type.

        Returns
        -------
        dict[str, Any]
            Mapped form data: {target_field_name: value}
            Values are pre-processed (date formatting, gender normalization, etc.).

        Raises
        ------
        FormFillerError
            If country_code is unsupported or required fields are missing.
        """
        country_code = country_code.upper()
        # Lookup is case-insensitive (YAML keys are lowercase)
        countries = self._countries()
        country_mapping = countries.get(country_code) or countries.get(country_code.lower())

        if not country_mapping:
            raise FormFillerError(f"Unsupported country: {country_code}")

        visa_types = country_mapping.get("visa_types", {})
        if not visa_types:
            raise FormFillerError(f"No visa types defined for {country_code}")

        # Resolve visa type
        if visa_type is None:
            visa_type = list(visa_types.keys())[0]
        elif visa_type not in visa_types:
            raise FormFillerError(
                f"Unknown visa type '{visa_type}' for {country_code}. "
                f"Available: {list(visa_types.keys())}"
            )

        field_map = visa_types[visa_type]
        field_defaults = country_mapping.get("field_defaults", {})

        # Check required fields
        required = self.get_required_fields(country_code, visa_type)
        missing = [f for f in required if f not in passport_data or passport_data[f] is None]
        if missing:
            raise FormFillerError(
                f"Missing required passport fields for {country_code}/{visa_type}: {missing}"
            )

        result: dict[str, Any] = {}

        for passport_field, target_field in field_map.items():
            value = passport_data.get(passport_field)

            if value is None:
                # Apply default if configured
                if passport_field in field_defaults:
                    result[target_field] = field_defaults[passport_field]
                continue

            # Date transformation
            if self._is_date_field(passport_field) and isinstance(value, (str, date, datetime)):
                fmt = country_mapping.get("date_fmt", "%d/%m/%Y")
                result[target_field] = self._format_date(value, fmt)
            # Gender normalization
            elif self._is_gender_field(passport_field):
                gm = country_mapping.get("gender_map", {})
                result[target_field] = gm.get(str(value).strip(), str(value))
            # Nationality translation (ISO code → English name)
            elif passport_field == "nationality":
                nationality_map = self._mapping.get("nationality_map", {}).get(str(value).upper())
                if nationality_map:
                    result[target_field] = nationality_map
                else:
                    result[target_field] = str(value)
            # Email - lowercase
            elif passport_field == "email" and isinstance(value, str):
                result[target_field] = value.lower().strip()
            # Phone - strip non-digits except +
            elif passport_field == "phone" and isinstance(value, str):
                result[target_field] = value.strip()
            # Concatenate if target already has value (e.g. surname + given_names → fullname)
            elif target_field in result:
                result[target_field] = f"{result[target_field]} {value}".strip()
            # General passthrough
            else:
                result[target_field] = value

        # Apply any field defaults not already set
        for key, default_val in field_defaults.items():
            target_keys = [v for k, v in field_map.items() if k == key]
            if target_keys and target_keys[0] not in result:
                result[target_keys[0]] = default_val

        logger.info(
            "Mapped %d fields for %s/%s -> %d output fields",
            len(passport_data), country_code, visa_type, len(result)
        )
        return result

    def submit_form(
        self,
        session: Any,
        form_data: dict[str, Any],
        submit_url: Optional[str] = None,
    ) -> FormSubmitResult:
        """
        Submit a filled form via HTTP session.

        Parameters
        ----------
        session : Union[requests.Session, httpx.Session]
            HTTP session with cookies (simulated in mock mode).
        form_data : dict[str, Any]
            Mapped form data from map_fields().
        submit_url : Optional[str]
            Submission URL. If None, uses the config-defined URL.

        Returns
        -------
        FormSubmitResult
            Submission result with success status, message, and order reference.
        """
        if self.mock_mode:
            return self._mock_submit(form_data)

        import requests

        timeout = self._config.get("timeouts", {}).get("submit_timeout", 60)

        try:
            response = session.post(
                submit_url,
                data=form_data,
                timeout=timeout,
                allow_redirects=False,
            )

            if response.status_code in (200, 201, 302, 303):
                # Try to extract confirmation number from response
                confirmation = self._extract_confirmation_no(response.text)
                return FormSubmitResult(
                    success=True,
                    message="Form submitted successfully",
                    confirmation_no=confirmation,
                    raw_response={"status_code": response.status_code},
                    status_code=response.status_code,
                )
            else:
                return FormSubmitResult(
                    success=False,
                    message=f"Submission failed with HTTP {response.status_code}",
                    status_code=response.status_code,
                )

        except Exception as exc:
            logger.error("Form submission error: %s", exc)
            return FormSubmitResult(
                success=False,
                message=f"Submission error: {exc}",
            )

    # ------------------------------------------------------------------ #
    # Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _is_date_field(self, field_name: str) -> bool:
        """Check if a passport field represents a date."""
        return any(kw in field_name.lower() for kw in ("date", "dob", "birth", "expiry", "arrival"))

    def _is_gender_field(self, field_name: str) -> bool:
        """Check if a field represents gender."""
        return any(kw in field_name.lower() for kw in ("sex", "gender"))

    def _format_date(
        self,
        value: Union[str, date, datetime],
        fmt: str,
    ) -> str:
        """Format a date value to the target format string."""
        if isinstance(value, str):
            # Try common input formats
            for input_fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    parsed = datetime.strptime(value, input_fmt)
                    return parsed.strftime(fmt)
                except ValueError:
                    continue
            return value  # Return as-is if parsing fails
        elif isinstance(value, datetime):
            return value.strftime(fmt)
        elif isinstance(value, date):
            return value.strftime(fmt)
        return str(value)

    def _extract_confirmation_no(self, html: str) -> Optional[str]:
        """Extract confirmation number from response HTML."""
        import re
        patterns = [
            r'confirmation[_\-]?no[_\-:]*\s*([A-Z0-9]{6,20})',
            r'order[_\-]?ref[_\-:]*\s*([A-Z0-9]{6,20})',
            r'application[_\-]?no[_\-:]*\s*([A-Z0-9]{6,20})',
            r'([A-Z]{2,3}[0-9]{6,12})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _mock_submit(self, form_data: dict[str, Any]) -> FormSubmitResult:
        """Mock form submission for development/testing."""
        import uuid
        confirmation = f"CONF-{uuid.uuid4().hex[:8].upper()}"
        logger.info("Mock submit: %s -> confirmation=%s", list(form_data.keys()), confirmation)
        return FormSubmitResult(
            success=True,
            message="Form submitted successfully (mock mode)",
            confirmation_no=confirmation,
            order_ref=confirmation,
            raw_response={"mock": True, "fields_submitted": len(form_data)},
            status_code=200,
        )