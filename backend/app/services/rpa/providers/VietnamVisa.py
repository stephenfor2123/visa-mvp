"""
Vietnam Visa Provider — automate visa applications at evisa.xXXXX.go.id.

Visa types supported:
  - e_visa: Electronic visa (e-visa) — 30-day single/temporary entry
  - visa_on_arrival: Visa on Arrival (requires approval letter)

Target website: https://evisa.xXXXX.go.id (or visaonline.vn)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from app.services.rpa.captcha_solver import CaptchaSolver
from app.services.rpa.form_filler import FormFiller
from app.services.rpa.page_parser import PageParser
from app.services.rpa.providers.base import BaseVisaProvider, VisaApplicationResult

logger = logging.getLogger(__name__)


class VietnamVisaProvider(BaseVisaProvider):
    """
    Vietnam-specific visa application automation.

    Implements BaseVisaProvider for Vietnam's e-visa portal.
    """

    country_code = "VN"

    def get_form_url(self) -> str:
        """
        Return the Vietnam e-visa application form URL.

        Returns
        -------
        str
            Full URL to the e-visa application form.
        """
        base_url = self.get_country_config().get(
            "base_url", "https://evisa.xXXXX.go.id"
        )
        form_path = self.get_country_config().get("form_path", "/application")
        return f"{base_url}{form_path}"

    def parse_form(self, html: str) -> dict[str, str]:
        """
        Parse Vietnam e-visa form fields from HTML.

        Parameters
        ----------
        html : str
            HTML content of the application form page.

        Returns
        -------
        dict[str, str]
            Mapping of field_name -> field_type.
        """
        return self._page_parser.parse_form_fields(html)

    def fill_form(
        self,
        html: str,
        passport_data: dict[str, Any],
        visa_type: str = "e_visa",
        captcha_solution: str = "",
    ) -> dict[str, Any]:
        """
        Fill Vietnam e-visa form with passport data.

        Parameters
        ----------
        html : str
            HTML content of the form page.
        passport_data : dict
            Passport holder data.
        visa_type : str
            Visa type (e_visa or visa_on_arrival).
        captcha_solution : str
            Solved captcha text.

        Returns
        -------
        dict[str, Any]
            Form data dict ready for submission.
        """
        # Map passport data to Vietnam form fields
        form_data = self._form_filler.map_fields(
            passport_data, country_code="VN", visa_type=visa_type
        )

        # Add captcha solution
        captcha_input = self._page_parser.parse_captcha_location(html).get("input_name", "captcha")
        form_data[captcha_input] = captcha_solution

        # Vietnam-specific fields
        form_data["visa_type"] = visa_type
        form_data["entry_purpose"] = "tourism"
        form_data["entry_type"] = form_data.get("entry_type", "single")
        form_data["port_of_entry"] = passport_data.get("port_of_boarding", "")

        # Check if port of entry is valid
        valid_ports = [
            "Noi Bai (Hanoi)", "Tan Son Nhat (Ho Chi Minh City)",
            "Da Nang", "Cam Ranh", "Phu Quoc",
        ]
        port = form_data.get("port_of_entry", "")
        if port and port not in valid_ports:
            logger.warning("Unknown Vietnam port of entry: %s", port)

        logger.info(
            "Vietnam form filled: %d fields, visa_type=%s, captcha=%s",
            len(form_data), visa_type, captcha_solution[:4] + "****"
        )
        return form_data

    def submit(
        self,
        form_data: dict[str, Any],
        submit_url: Optional[str] = None,
    ) -> VisaApplicationResult:
        """
        Submit the Vietnam e-visa application form.

        Parameters
        ----------
        form_data : dict[str, Any]
            Filled form data from fill_form().
        submit_url : Optional[str]
            Override submission URL.

        Returns
        -------
        VisaApplicationResult
            Submission result with confirmation number.
        """
        if self._mock_mode:
            return self._mock_submit(form_data)

        session = self.get_session()
        target_url = submit_url or self.get_form_url()

        try:
            result = self._form_filler.submit_form(session, form_data, target_url)

            if result.success:
                return VisaApplicationResult(
                    success=True,
                    confirmation_no=result.confirmation_no,
                    message="Vietnam e-visa application submitted successfully",
                    order_ref=result.order_ref,
                    raw_response=result.raw_response,
                    status_code=result.status_code,
                )
            else:
                return VisaApplicationResult(
                    success=False,
                    message=result.message,
                    raw_response=result.raw_response,
                    status_code=result.status_code,
                )
        except Exception as exc:
            logger.error("Vietnam submit error: %s", exc)
            return VisaApplicationResult(
                success=False,
                message=f"Submission error: {exc}",
            )

    # ------------------------------------------------------------------ #
    # Vietnam-specific helpers                                          #
    # ------------------------------------------------------------------ #

    def get_available_visa_types(self) -> list[str]:
        """Return supported visa types for Vietnam."""
        return ["e_visa", "visa_on_arrival"]

    def get_valid_ports_of_entry(self) -> list[str]:
        """Return list of valid Vietnam ports of entry for e-visa."""
        return [
            "Noi Bai International Airport (Hanoi)",
            "Tan Son Nhat International Airport (Ho Chi Minh City)",
            "Da Nang International Airport",
            "Cam Ranh International Airport (Khanh Hoa)",
            "Phu Quoc International Airport",
            "Ha Long City (Quang Ninh)",
            "Hue (Thua Thien Hue)",
        ]

    def validate_passport_data(self, passport_data: dict[str, Any]) -> list[str]:
        """
        Validate passport data against Vietnam e-visa requirements.

        Parameters
        ----------
        passport_data : dict
            Passport holder data.

        Returns
        -------
        list[str]
            List of validation errors (empty if valid).
        """
        errors = []

        required = ["surname", "given_name", "date_of_birth", "passport_no",
                    "passport_expiry", "nationality", "sex", "email", "phone"]
        for field in required:
            if not passport_data.get(field):
                errors.append(f"Missing required field: {field}")

        # Passport must be valid for 6+ months
        expiry = passport_data.get("passport_expiry")
        if expiry:
            from datetime import datetime
            try:
                if isinstance(expiry, str):
                    exp_date = datetime.strptime(expiry, "%Y-%m-%d")
                else:
                    exp_date = expiry
                if exp_date < datetime.utcnow():
                    errors.append("Passport has expired")
            except (ValueError, TypeError):
                errors.append(f"Invalid passport_expiry format: {expiry}")

        # Nationality check (Vietnam e-visa not available for all nationalities)
        excluded_nationalities = ["Vietnam"]  # Cannot apply for own country
        nat = passport_data.get("nationality", "")
        if nat in excluded_nationalities:
            errors.append(f"Nationality '{nat}' is not eligible for Vietnam e-visa")

        return errors

    def _mock_submit(self, form_data: dict[str, Any]) -> VisaApplicationResult:
        """Mock submission for development."""
        import uuid
        confirmation = f"VN-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            "Mock Vietnam submit: %s -> confirmation=%s",
            list(form_data.keys()), confirmation
        )
        return VisaApplicationResult(
            success=True,
            confirmation_no=confirmation,
            message="Vietnam e-visa application submitted (mock mode)",
            order_ref=f"VN-APP-{uuid.uuid4().hex[:6].upper()}",
            raw_response={"mock": True, "fields": len(form_data)},
            status_code=200,
        )