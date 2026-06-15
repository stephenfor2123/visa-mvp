"""
Indonesia Visa Provider — automate visa applications at immigration.go.id.

Visa types supported:
  - visit_visa: B211A single-entry tourist visa (30 days)
  - on_arrival: Visa on Arrival (VOA) — limited nationalities
  - diplomatic: Diplomatic/service passport holders

Target website: https://visa-online.imigration.go.id
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


class IndonesiaVisaProvider(BaseVisaProvider):
    """
    Indonesia-specific visa application automation.

    Implements BaseVisaProvider for Indonesia's online visa portal.
    """

    country_code = "ID"

    def get_form_url(self) -> str:
        """
        Return the Indonesia visa application form URL.

        Returns
        -------
        str
            Full URL to the visa application form.
        """
        base_url = self.get_country_config().get(
            "base_url", "https://visa-online.imigration.go.id"
        )
        form_path = self.get_country_config().get("form_path", "/apply")
        return f"{base_url}{form_path}"

    def parse_form(self, html: str) -> dict[str, str]:
        """
        Parse Indonesia visa form fields from HTML.

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
        visa_type: str = "visit_visa",
        captcha_solution: str = "",
    ) -> dict[str, Any]:
        """
        Fill Indonesia visa form with passport data.

        Parameters
        ----------
        html : str
            HTML content of the form page.
        passport_data : dict
            Passport holder data.
        visa_type : str
            Visa type (visit_visa, on_arrival, diplomatic).
        captcha_solution : str
            Solved captcha text.

        Returns
        -------
        dict[str, Any]
            Form data dict ready for submission.
        """
        # Map passport data to Indonesia form fields
        form_data = self._form_filler.map_fields(
            passport_data, country_code="ID", visa_type=visa_type
        )

        # Add captcha solution
        captcha_input = self._page_parser.parse_captcha_location(html).get("input_name", "captcha")
        form_data[captcha_input] = captcha_solution

        # Indonesia-specific fields
        form_data["visa_purpose"] = form_data.get("visa_purpose", "Tourism")
        form_data["entry_type"] = form_data.get("entry_type", "single")
        form_data["duration_stay"] = form_data.get("duration_days", 30)

        # Airline info (often required)
        if "flight_no" not in form_data:
            form_data["flight_number"] = passport_data.get("flight_no", "")

        logger.info(
            "Indonesia form filled: %d fields, visa_type=%s, captcha=%s",
            len(form_data), visa_type, captcha_solution[:4] + "****"
        )
        return form_data

    def submit(
        self,
        form_data: dict[str, Any],
        submit_url: Optional[str] = None,
    ) -> VisaApplicationResult:
        """
        Submit the Indonesia visa application form.

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
                    message="Indonesia visa application submitted successfully",
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
            logger.error("Indonesia submit error: %s", exc)
            return VisaApplicationResult(
                success=False,
                message=f"Submission error: {exc}",
            )

    # ------------------------------------------------------------------ #
    # Indonesia-specific helpers                                         #
    # ------------------------------------------------------------------ #

    def get_available_visa_types(self) -> list[str]:
        """Return supported visa types for Indonesia."""
        return ["visit_visa", "on_arrival", "diplomatic"]

    def validate_passport_data(self, passport_data: dict[str, Any]) -> list[str]:
        """
        Validate passport data against Indonesia requirements.

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

        # Required fields
        required = ["surname", "given_name", "date_of_birth", "passport_no",
                    "passport_expiry", "nationality", "sex", "email", "phone"]
        for field in required:
            if not passport_data.get(field):
                errors.append(f"Missing required field: {field}")

        # Passport validity: must be valid for 6+ months from travel date
        expiry = passport_data.get("passport_expiry")
        if expiry:
            from datetime import datetime
            try:
                if isinstance(expiry, str):
                    exp_date = datetime.strptime(expiry, "%Y-%m-%d")
                else:
                    exp_date = expiry
                # Rough check: expiry should be in the future
                if exp_date < datetime.utcnow():
                    errors.append("Passport has expired")
            except (ValueError, TypeError):
                errors.append(f"Invalid passport_expiry format: {expiry}")

        return errors

    def _mock_submit(self, form_data: dict[str, Any]) -> VisaApplicationResult:
        """Mock submission for development."""
        import uuid
        confirmation = f"ID-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            "Mock Indonesia submit: %s -> confirmation=%s",
            list(form_data.keys()), confirmation
        )
        return VisaApplicationResult(
            success=True,
            confirmation_no=confirmation,
            message="Indonesia visa application submitted (mock mode)",
            order_ref=f"ID-APP-{uuid.uuid4().hex[:6].upper()}",
            raw_response={"mock": True, "fields": len(form_data)},
            status_code=200,
        )