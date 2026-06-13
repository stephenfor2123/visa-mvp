"""
tests/integration/test_ocr_field_mapping.py
V2 §5.1.3 — 9-country passport OCR field mapping schema smoke test
"""
import re
from pathlib import Path

import pytest
import yaml


def test_field_mapping_9countries():
    """
    Verify ocr_field_mapping.yaml loads all 9 countries and each has a
    non-empty passport_re regex that is a valid pattern.
    """
    yaml_path = Path(__file__).parents[2] / "app" / "services" / "ocr_field_mapping.yaml"
    assert yaml_path.exists(), f"ocr_field_mapping.yaml not found at {yaml_path}"

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    expected = {"us", "jp", "gb", "au", "sg", "de", "fr", "it", "kr"}
    assert set(data.keys()) == expected, f"Country keys mismatch: {set(data.keys())}"

    for country, cfg in data.items():
        # passport_re must be present and non-empty
        assert "passport_re" in cfg, f"[{country}] missing passport_re"
        assert cfg["passport_re"], f"[{country}] passport_re is empty"

        # passport_re must be a valid regex (compile without error)
        try:
            re.compile(cfg["passport_re"])
        except re.error as e:
            pytest.fail(f"[{country}] passport_re is invalid regex: {e}")

        # date_fmt must be present and non-empty
        assert "date_fmt" in cfg, f"[{country}] missing date_fmt"
        assert cfg["date_fmt"], f"[{country}] date_fmt is empty"

        # surname_pos must be present
        assert "surname_pos" in cfg, f"[{country}] missing surname_pos"

        # given_name_pos must be present
        assert "given_name_pos" in cfg, f"[{country}] missing given_name_pos"

        # gender_map must be present and non-empty
        assert "gender_map" in cfg, f"[{country}] missing gender_map"
        assert cfg["gender_map"], f"[{country}] gender_map is empty"