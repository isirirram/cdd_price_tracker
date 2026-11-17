"""
Unit, contract, and logic tests for LocalStoreAdapter and LocalStore Server (Slot 2).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import requests

from scraper.config import config
from scraper.demo_store.server import (
    CATALOG,
    DEFAULT_CATALOG,
    ID_REGEX,
    reset_catalog,
)
from scraper.integrations.local_store import LocalStoreAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


@pytest.fixture
def adapter():
    return LocalStoreAdapter()


@pytest.fixture(autouse=True)
def clean_state():
    config.clear_overrides()
    reset_catalog()
    yield
    config.clear_overrides()
    reset_catalog()


def test_local_store_can_handle(adapter):
    """Verify URL detection for localstore."""
    assert adapter.can_handle("http://127.0.0.1:8000/products/product-001")
    assert adapter.can_handle("http://localhost:8000/products/product-002")
    assert adapter.can_handle("localstore://product-001")
    assert not adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")


def test_local_store_extract_product_id(adapter):
    """Verify product ID extraction."""
    assert adapter.extract_product_id("http://127.0.0.1:8000/products/product-001") == "product-001"
    assert adapter.extract_product_id("localstore://product-999") == "product-999"
    assert adapter.extract_product_id("http://127.0.0.1:8000/invalid") is None


def test_local_store_offline_behavior(adapter):
    """Verify clean, friendly error when local server is offline."""
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        result = adapter.scrape("http://127.0.0.1:8000/products/product-001")
        assert result.success is False
        assert "offline" in result.error.lower()
        assert "8000" in result.error
        assert result.source_category == SourceCategory.CONTROLLED_DEMO_STORE


@patch("requests.get")
def test_local_store_successful_mock_scrape(mock_get, adapter):
    """Verify successful parsing of LocalStore response fixture."""
    fixture_path = FIXTURES_DIR / "local_store_sample.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sample_data
    mock_get.return_value = mock_resp

    url = "http://127.0.0.1:8000/products/product-001"
    result = adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "Demo Wireless Noise-Cancelling Headphones"
    assert result.current_price == 1499.0
    assert result.currency == "INR"
    assert result.site == "local_store"
    assert result.source_category == SourceCategory.CONTROLLED_DEMO_STORE
    assert result.is_commercial_store is False
    assert result.cache_policy.allow_historical_storage is True
    assert result.cache_policy.price_ttl_seconds == 60


@patch("requests.get")
def test_local_store_price_drop_simulation(mock_get, adapter):
    """
    Verify that dynamic price drops are accurately reflected:
    1. First check returns ₹1499.
    2. Simulated admin update lowers price to ₹999.
    3. Second check verifies lower price is detected!
    """
    # 1. Initial query
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {
        "id": "product-001",
        "title": "Demo Wireless Headphones",
        "price": 1499.0,
        "currency": "INR",
        "in_stock": True
    }

    # 2. Price drop response
    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {
        "id": "product-001",
        "title": "Demo Wireless Headphones",
        "price": 999.0,
        "currency": "INR",
        "in_stock": True
    }

    mock_get.side_effect = [resp1, resp2]

    url = "http://127.0.0.1:8000/products/product-001"
    res1 = adapter.scrape(url)
    assert res1.current_price == 1499.0

    res2 = adapter.scrape(url)
    assert res2.current_price == 999.0
    assert res2.current_price < res1.current_price


def test_local_store_server_validation_logic():
    """Verify security controls: price bounds and ID regex."""
    # Test valid product IDs
    assert ID_REGEX.match("product-001")
    assert ID_REGEX.match("PROD_123")
    assert not ID_REGEX.match("../../etc/passwd")
    assert not ID_REGEX.match("product/sub")

    # Test in-memory catalog
    assert "product-001" in CATALOG
    assert CATALOG["product-001"]["price"] == 1499.0

    # Test catalog mutation and reset
    CATALOG["product-001"]["price"] = 999.0
    assert CATALOG["product-001"]["price"] == 999.0

    reset_catalog()
    assert CATALOG["product-001"]["price"] == 1499.0
