"""
Unit and contract tests for AmazonCreatorsAdapter (Slot 3).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scraper.config import config
from scraper.integrations.amazon import AmazonCreatorsAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


@pytest.fixture
def adapter():
    return AmazonCreatorsAdapter()


@pytest.fixture(autouse=True)
def clean_config():
    config.clear_overrides()
    yield
    config.clear_overrides()


def test_amazon_can_handle(adapter):
    """Verify Amazon India URL detection."""
    assert adapter.can_handle("https://www.amazon.in/dp/B08L5W4SW6")
    assert adapter.can_handle("https://amzn.in/d/123456")
    assert adapter.can_handle("asin:B08L5W4SW6")
    assert not adapter.can_handle("https://flipkart.com/item")


def test_amazon_extract_product_id(adapter):
    """Verify ASIN extraction across URL structures."""
    assert adapter.extract_product_id("https://www.amazon.in/dp/B08L5W4SW6") == "B08L5W4SW6"
    assert adapter.extract_product_id("https://www.amazon.in/Product-Title/dp/B08L5W4SW6/ref=sr_1_1") == "B08L5W4SW6"
    assert adapter.extract_product_id("asin:b08l5w4sw6") == "B08L5W4SW6"
    assert adapter.extract_product_id("https://www.amazon.in/invalid-page") is None


def test_amazon_missing_credentials_handling(adapter):
    """Verify clean credential-gated failure when environment variables are unset."""
    config.set_override("amazon_credential_id", None)
    config.set_override("amazon_credential_secret", None)

    result = adapter.scrape("https://www.amazon.in/dp/B08L5W4SW6")
    assert result.success is False
    assert "credentials missing" in result.error.lower()
    assert "10 qualifying sales" in result.error.lower()
    assert result.source_category == SourceCategory.CREDENTIAL_GATED
    assert result.is_commercial_store is True
    # Verify strict cache retention restrictions
    assert result.cache_policy.allow_historical_storage is False
    assert result.cache_policy.price_ttl_seconds == 3600


@patch("requests.post")
def test_amazon_successful_mock_creators_api_response(mock_post, adapter):
    """Verify parsing of official Amazon Creators API response fixture."""
    fixture_path = FIXTURES_DIR / "amazon_creators_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_api_data = json.load(f)

    # 1. Mock OAuth token response
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {"access_token": "mock_bearer_token_123", "expires_in": 3600}

    # 2. Mock Creators API response
    api_resp = MagicMock()
    api_resp.status_code = 200
    api_resp.json.return_value = sample_api_data

    mock_post.side_effect = [token_resp, api_resp]

    config.set_override("amazon_credential_id", "test_id")
    config.set_override("amazon_credential_secret", "test_secret")

    url = "https://www.amazon.in/dp/B08L5W4SW6"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "Apple iPhone 12 (128GB) - Blue"
    assert result.current_price == 49999.0
    assert result.currency == "INR"
    assert result.image_url == "https://m.media-amazon.com/images/I/71ZOtNdaZCL._SL1500_.jpg"
    assert result.site == "amazon"
    assert result.source_category == SourceCategory.CREDENTIAL_GATED
    assert result.is_commercial_store is True
    assert result.cache_policy.allow_historical_storage is False
    assert result.cache_policy.price_ttl_seconds == 3600
    assert result.cache_policy.metadata_ttl_seconds == 86400


@patch("requests.post")
def test_amazon_missing_image_returns_none(mock_post, adapter):
    """Verify that an API response without images cleanly sets image_url to None."""
    token_resp = MagicMock()
    token_resp.status_code = 200
    token_resp.json.return_value = {"access_token": "mock_bearer_token_123", "expires_in": 3600}

    api_resp = MagicMock()
    api_resp.status_code = 200
    api_resp.json.return_value = {
        "itemsResult": {
            "items": [
                {
                    "asin": "B08L5W4SW6",
                    "itemInfo": {"title": {"displayValue": "Apple iPhone without Image"}},
                    "offersV2": {"listings": [{"price": {"amount": 45000.0, "currency": "INR"}}]}
                }
            ]
        }
    }
    mock_post.side_effect = [token_resp, api_resp]

    config.set_override("amazon_credential_id", "test_id")
    config.set_override("amazon_credential_secret", "test_secret")

    result = adapter.scrape("https://www.amazon.in/dp/B08L5W4SW6")
    assert result.success is True
    assert result.current_price == 45000.0
    assert result.image_url is None

