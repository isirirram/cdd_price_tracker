"""
Unit and mock tests for OpenPricesAdapter (Slot 1).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests

from scraper.integrations.open_prices import OpenPricesAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


@pytest.fixture
def adapter():
    return OpenPricesAdapter()


def test_open_prices_can_handle(adapter):
    """Verify URL detection logic."""
    assert adapter.can_handle("https://in.openfoodfacts.org/product/8901030825347")
    assert adapter.can_handle("https://prices.openfoodfacts.org/prices?product_code=8901030825347")
    assert adapter.can_handle("barcode:8901030825347")
    assert adapter.can_handle("openprices://8901030825347")
    assert adapter.can_handle("8901030825347")
    assert not adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")


def test_open_prices_extract_product_id(adapter):
    """Verify barcode extraction across supported formats."""
    assert adapter.extract_product_id("https://in.openfoodfacts.org/product/8901030825347/tea") == "8901030825347"
    assert adapter.extract_product_id("https://prices.openfoodfacts.org/prices?product_code=8901030825347") == "8901030825347"
    assert adapter.extract_product_id("barcode:8901030825347") == "8901030825347"
    assert adapter.extract_product_id("openprices://8901030825347") == "8901030825347"
    assert adapter.extract_product_id("https://in.openfoodfacts.org/invalid-url") is None


def test_open_prices_invalid_barcode_returns_failure(adapter):
    """Verify that an invalid URL returns failure without making API calls."""
    res = adapter.scrape("https://in.openfoodfacts.org/product/no-barcode-here")
    assert res.success is False
    assert "Invalid Open Prices URL" in res.error
    assert res.source_category == SourceCategory.OPEN_DATA_OBSERVATION


@patch("requests.get")
def test_open_prices_successful_mock_scrape(mock_get, adapter):
    """Verify successful parsing using official Open Prices JSON fixture."""
    fixture_path = FIXTURES_DIR / "open_prices_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_data
    mock_get.return_value = mock_resp

    url = "https://in.openfoodfacts.org/product/8901030825347"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "Tata Tea Gold 500g"
    assert result.current_price == 310.0
    assert result.currency == "INR"
    assert result.source_category == SourceCategory.OPEN_DATA_OBSERVATION
    assert result.is_commercial_store is False
    assert result.cache_policy.allow_historical_storage is True
    assert result.cache_policy.price_ttl_seconds == 86400
    assert "ODbL 1.0" in result.attribution


@patch("requests.get")
def test_open_prices_zero_observations_recorded(mock_get, adapter):
    """Verify graceful handling when product code exists but has no prices."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"items": [], "total": 0}
    mock_get.return_value = mock_resp

    url = "barcode:8901030825347"
    result = adapter.scrape(url)

    assert result.success is False
    assert "zero price observations" in result.error.lower()
    assert result.cache_policy.allow_historical_storage is True


@patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout"))
def test_open_prices_timeout_handling(mock_get, adapter):
    """Verify timeout is caught and converted to failure result."""
    result = adapter.scrape("barcode:8901030825347")
    assert result.success is False
    assert "timeout" in result.error.lower()

