"""
Unit, contract, and resilience tests for WooCommerceAdapter (Slot 7).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scraper.integrations.woocommerce import WooCommerceAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


@pytest.fixture
def adapter():
    return WooCommerceAdapter()


def test_woocommerce_can_handle(adapter):
    """Verify WooCommerce URL detection."""
    assert adapter.can_handle("https://example.com/product/flying-ninja/")
    assert adapter.can_handle("https://woocommerce.store.com/product/hoodie")
    assert adapter.can_handle("https://store.com/?product=123")
    assert adapter.can_handle("woocommerce://store.com/product/hoodie")
    assert not adapter.can_handle("https://myntra.com/shoes/p/999")
    assert not adapter.can_handle("https://ajio.com/product/1234")
    assert not adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")


def test_woocommerce_extract_product_id(adapter):
    """Verify product slug / ID extraction."""
    assert adapter.extract_product_id("https://example.com/product/flying-ninja/") == "flying-ninja"
    assert adapter.extract_product_id("https://example.com/?product=99") == "99"
    assert adapter.extract_product_id("woocommerce://example.com/product/hoodie") == "hoodie"
    assert adapter.extract_product_id("https://example.com/contact-us") is None


@patch("scraper.security.safe_get")
def test_woocommerce_successful_mock_scrape(mock_safe_get, adapter):
    """Verify parsing of official WooCommerce Store API response fixture."""
    fixture_path = FIXTURES_DIR / "woocommerce_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_data
    mock_safe_get.return_value = mock_resp

    url = "https://example.com/product/flying-ninja/"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "Flying Ninja Hoodie"
    # 249900 minor units (2 decimal places) -> 2499.0 INR
    assert result.current_price == 2499.0
    assert result.currency == "INR"
    assert result.image_url == "https://example.com/wp-content/uploads/2026/01/hoodie-ninja-front.jpg"
    assert result.site == "woocommerce"
    assert result.source_category == SourceCategory.PUBLIC_STORE_API
    assert result.is_commercial_store is True
    assert result.cache_policy.allow_historical_storage is True
    assert result.cache_policy.price_ttl_seconds == 3600


@patch("scraper.security.safe_get")
def test_woocommerce_numeric_id_query(mock_safe_get, adapter):
    """Verify querying numeric product ID uses /wp-json/wc/store/v1/products/{id}."""
    fixture_path = FIXTURES_DIR / "woocommerce_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    # Return single dict for direct ID query
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_data[0]
    mock_safe_get.return_value = mock_resp

    url = "https://example.com/?product=99"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "Flying Ninja Hoodie"
    assert result.current_price == 2499.0
    # Verify endpoint called directly with numeric ID
    mock_safe_get.assert_called_once()
    called_endpoint = mock_safe_get.call_args[0][0]
    assert "/products/99" in called_endpoint


@patch("scraper.security.safe_get")
def test_woocommerce_not_found_handling(mock_safe_get, adapter):
    """Verify clean 404 handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_safe_get.return_value = mock_resp

    result = adapter.scrape("https://example.com/product/missing-item")
    assert result.success is False
    assert "404" in result.error
    assert "missing-item" in result.error


@patch("scraper.security.safe_get")
def test_woocommerce_disabled_store_api_handling(mock_safe_get, adapter):
    """Verify clean handling when WooCommerce Store API is blocked (403/401)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_safe_get.return_value = mock_resp

    result = adapter.scrape("https://example.com/product/secret-item")
    assert result.success is False
    assert "disabled" in result.error.lower() or "restricted" in result.error.lower()


def test_woocommerce_ssrf_rejection(adapter):
    """Verify localhost / private IP WooCommerce URLs are blocked by SSRF checks."""
    result = adapter.scrape("http://localhost:8000/product/flying-ninja")
    assert result.success is False
    assert "security rejection" in result.error.lower()
