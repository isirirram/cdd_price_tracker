"""
Unit, contract, and resilience tests for ShopifyAdapter (Slot 6).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests

from scraper.integrations.shopify import ShopifyAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


@pytest.fixture
def adapter():
    return ShopifyAdapter()


def test_shopify_can_handle(adapter):
    """Verify Shopify URL recognition."""
    assert adapter.can_handle("https://store.myshopify.com/products/all-mountain-snowboard")
    assert adapter.can_handle("https://shop.gymshark.com/products/crest-hoodie")
    assert adapter.can_handle("https://store.com/collections/winter/products/snowboard")
    assert adapter.can_handle("shopify://store.myshopify.com/products/snowboard")
    assert not adapter.can_handle("https://myntra.com/shoes/p/999")
    assert not adapter.can_handle("https://ajio.com/product/1234")
    assert not adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")


def test_shopify_extract_product_id(adapter):
    """Verify product handle extraction."""
    assert adapter.extract_product_id("https://store.myshopify.com/products/all-mountain-snowboard") == "all-mountain-snowboard"
    assert adapter.extract_product_id("https://store.com/products/snowboard?variant=804171196") == "snowboard"
    assert adapter.extract_product_id("https://store.com/products/snowboard.js") == "snowboard"
    assert adapter.extract_product_id("shopify://store.com/products/cool-jacket") == "cool-jacket"
    assert adapter.extract_product_id("https://store.com/about-us") is None


@patch("scraper.security.safe_get")
def test_shopify_successful_mock_scrape(mock_safe_get, adapter):
    """Verify parsing of official Shopify Ajax API JSON fixture."""
    fixture_path = FIXTURES_DIR / "shopify_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_data
    mock_safe_get.return_value = mock_resp

    url = "https://store.myshopify.com/products/the-all-mountain-snowboard"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "The All-Mountain Snowboard"
    # 2499900 minor units (cents/paise) -> 24999.0 INR
    assert result.current_price == 24999.0
    assert result.currency == "INR"
    assert result.image_url == "https://cdn.shopify.com/s/files/1/0001/products/snowboard-blue.jpg"
    assert result.site == "shopify"
    assert result.source_category == SourceCategory.PUBLIC_STORE_API
    assert result.is_commercial_store is True
    assert result.cache_policy.allow_historical_storage is True
    assert result.cache_policy.price_ttl_seconds == 3600


@patch("scraper.security.safe_get")
def test_shopify_variant_price_selection(mock_safe_get, adapter):
    """Verify extraction of specific variant price when ?variant=ID is in URL."""
    fixture_path = FIXTURES_DIR / "shopify_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_data
    mock_safe_get.return_value = mock_resp

    # Variant 804171197 has price 2899900 -> 28999.0
    url = "https://store.myshopify.com/products/the-all-mountain-snowboard?variant=804171197"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.current_price == 28999.0


@patch("scraper.security.safe_get")
def test_shopify_not_found_handling(mock_safe_get, adapter):
    """Verify clean 404 product not found handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_safe_get.return_value = mock_resp

    result = adapter.scrape("https://store.myshopify.com/products/discontinued-item")
    assert result.success is False
    assert "404" in result.error
    assert "discontinued-item" in result.error


@patch("scraper.security.safe_get")
def test_shopify_password_protected_handling(mock_safe_get, adapter):
    """Verify restricted/password-protected store handling."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_safe_get.return_value = mock_resp

    result = adapter.scrape("https://private-store.myshopify.com/products/secret-item")
    assert result.success is False
    assert "password-protected" in result.error.lower() or "restricted" in result.error.lower()


def test_shopify_ssrf_rejection(adapter):
    """Verify localhost / private IP Shopify URLs are blocked by SSRF checks."""
    result = adapter.scrape("http://localhost:8000/products/snowboard")
    assert result.success is False
    assert "security rejection" in result.error.lower()
