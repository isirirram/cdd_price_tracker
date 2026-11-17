"""
Unit and contract tests for FlipkartAffiliateAdapter (Slot 4).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scraper.config import config
from scraper.integrations.flipkart import FlipkartAffiliateAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


@pytest.fixture
def adapter():
    return FlipkartAffiliateAdapter()


@pytest.fixture(autouse=True)
def clean_config():
    config.clear_overrides()
    yield
    config.clear_overrides()


def test_flipkart_can_handle(adapter):
    """Verify Flipkart URL detection."""
    assert adapter.can_handle("https://www.flipkart.com/product/p/itm1234567890123")
    assert adapter.can_handle("https://dl.flipkart.com/dl/item?pid=MOBFWBYZ8637EKWB")
    assert adapter.can_handle("fsn:MOBFWBYZ8637EKWB")
    assert not adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")


def test_flipkart_extract_product_id(adapter):
    """Verify FSN/PID extraction from various Flipkart URL structures."""
    assert adapter.extract_product_id(
        "https://www.flipkart.com/apple-iphone-12/p/itm1234567890123?pid=MOBFWBYZ8637EKWB"
    ) == "MOBFWBYZ8637EKWB"

    assert adapter.extract_product_id(
        "https://dl.flipkart.com/dl/product/p/itmd0f8450f3b497"
    ) == "itmd0f8450f3b497"

    assert adapter.extract_product_id("fsn:mobfwbyz8637ekwb") == "mobfwbyz8637ekwb"
    assert adapter.extract_product_id("https://www.flipkart.com/helpcentre") is None


def test_flipkart_missing_credentials_handling(adapter):
    """Verify clean credential-gated failure when environment variables are unset."""
    config.set_override("flipkart_affiliate_id", None)
    config.set_override("flipkart_affiliate_token", None)

    result = adapter.scrape("https://www.flipkart.com/item?pid=MOBFWBYZ8637EKWB")
    assert result.success is False
    assert "credentials missing" in result.error.lower()
    assert "suspended" in result.error.lower()
    assert result.source_category == SourceCategory.CREDENTIAL_GATED
    assert result.is_commercial_store is True
    assert result.cache_policy.allow_historical_storage is False


@patch("requests.get")
def test_flipkart_successful_mock_affiliate_response(mock_get, adapter):
    """Verify parsing of official Flipkart Affiliate API response fixture."""
    fixture_path = FIXTURES_DIR / "flipkart_affiliate_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_data
    mock_get.return_value = mock_resp

    config.set_override("flipkart_affiliate_id", "test_affiliate_id")
    config.set_override("flipkart_affiliate_token", "test_token_123")

    url = "https://www.flipkart.com/item?pid=MOBFWBYZ8637EKWB"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "APPLE iPhone 12 (Blue, 128 GB)"
    assert result.current_price == 48999.0
    assert result.currency == "INR"
    assert result.site == "flipkart"
    assert result.source_category == SourceCategory.CREDENTIAL_GATED
    assert result.is_commercial_store is True
    assert result.cache_policy.allow_historical_storage is False
    assert result.cache_policy.price_ttl_seconds == 86400
