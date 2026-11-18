"""
Unit, contract, and resilience tests for BigCommerceAdapter (Slot 8).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scraper.integrations.bigcommerce import BigCommerceAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


@pytest.fixture
def adapter():
    return BigCommerceAdapter()


def test_bigcommerce_can_handle(adapter):
    """Verify BigCommerce URL detection."""
    assert adapter.can_handle("https://store.mybigcommerce.com/products/sample-item.html")
    assert adapter.can_handle("https://bigcommerce.example.com/item")
    assert adapter.can_handle("bigcommerce://store.mybigcommerce.com/products/sample")
    assert not adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")
    assert not adapter.can_handle("https://myntra.com/shoes/p/999")


def test_bigcommerce_extract_product_id(adapter):
    """Verify slug extraction from BigCommerce URLs."""
    assert adapter.extract_product_id("https://store.mybigcommerce.com/products/sample-item.html") == "sample-item"
    assert adapter.extract_product_id("https://store.mybigcommerce.com/running-shoes/") == "running-shoes"
    assert adapter.extract_product_id("bigcommerce://store.com/products/pro-gear") == "pro-gear"


@patch("scraper.security.safe_get")
def test_bigcommerce_successful_mock_scrape(mock_safe_get, adapter):
    """Verify parsing of BigCommerce public HTML/JSON-LD fixture."""
    fixture_path = FIXTURES_DIR / "bigcommerce_sample.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content
    mock_safe_get.return_value = mock_resp

    url = "https://store.mybigcommerce.com/products/pro-running-shoes"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "BigCommerce Pro Running Shoes"
    assert result.current_price == 3499.0
    assert result.currency == "INR"
    assert "running-shoes.jpg" in result.image_url
    assert result.site == "bigcommerce"
    assert result.source_category == SourceCategory.PUBLIC_STORE_API
    assert result.is_commercial_store is True
    assert result.cache_policy.allow_historical_storage is True
    assert result.cache_policy.price_ttl_seconds == 3600


@patch("scraper.security.safe_get")
def test_bigcommerce_authentication_required_handling(mock_safe_get, adapter):
    """Verify clear error when BigCommerce store requires authentication (HTTP 401/403)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_safe_get.return_value = mock_resp

    result = adapter.scrape("https://store.mybigcommerce.com/products/b2b-item")
    assert result.success is False
    assert "authentication" in result.error.lower() or "credentials" in result.error.lower()


@patch("scraper.security.safe_get")
def test_bigcommerce_not_found_handling(mock_safe_get, adapter):
    """Verify 404 handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_safe_get.return_value = mock_resp

    result = adapter.scrape("https://store.mybigcommerce.com/products/deleted-item")
    assert result.success is False
    assert "404" in result.error


def test_bigcommerce_ssrf_rejection(adapter):
    """Verify localhost / private IP BigCommerce URLs are blocked by SSRF checks."""
    result = adapter.scrape("http://localhost:8000/products/sample-item")
    assert result.success is False
    assert "security rejection" in result.error.lower()
