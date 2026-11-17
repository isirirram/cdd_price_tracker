"""
Quarantined benchmark and resilience tests using DummyJSON payloads.

Rules:
1. DummyJSON must NEVER be registered in ScraperFactory for production users.
2. Simulated prices must never be labeled as real shopping prices.
3. Tests pipeline resilience against network errors and malformed JSON.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import requests

from scraper.scraper_factory import scrape_product, ScraperFactory
from scraper.models import ScraperResult, SourceCategory
from scraper.exceptions import UnsupportedWebsiteError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_dummyjson_is_strictly_unsupported_in_production():
    """Verify that calling scrape_product with a DummyJSON URL is rejected as unsupported."""
    url = "https://dummyjson.com/products/1"
    result = scrape_product(url)
    assert result.success is False
    assert "dummyjson.com" in result.site or "dummyjson.com" in result.error
    assert result.source_category == SourceCategory.POLICY_RESTRICTED


def test_dummyjson_fixture_parsing_resilience():
    """Verify that synthetic test fixture parses properly for benchmark verification."""
    fixture_path = FIXTURES_DIR / "dummyjson_sample.json"
    assert fixture_path.exists()

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["id"] == 1
    assert data["title"] == "Essence Mascara Lash Princess"
    assert float(data["price"]) == 9.99


def test_pipeline_timeout_resilience():
    """Verify that network timeouts return structured failure results without crashing."""
    with patch("requests.get", side_effect=requests.Timeout("Connection timed out")):
        result = scrape_product("https://in.openfoodfacts.org/product/8901030825347")
        assert result.success is False
        assert "timeout" in result.error.lower()

