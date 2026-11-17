"""
Unit tests for CromaPolicyAdapter (Slot 5 - Policy-Restricted Platform).
"""

from unittest.mock import patch
import pytest

from scraper.integrations.croma import CromaPolicyAdapter
from scraper.models import SourceCategory


@pytest.fixture
def adapter():
    return CromaPolicyAdapter()


def test_croma_can_handle(adapter):
    """Verify Croma URL detection."""
    assert adapter.can_handle("https://www.croma.com/apple-iphone-15/p/270412")
    assert adapter.can_handle("http://croma.com/product/p/12345")
    assert not adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")


def test_croma_extract_product_id(adapter):
    """Verify product code extraction."""
    assert adapter.extract_product_id("https://www.croma.com/apple-iphone-15/p/270412") == "270412"


@patch("requests.get")
@patch("requests.post")
def test_croma_makes_zero_network_requests_and_refuses_scraping(mock_post, mock_get, adapter):
    """
    CRITICAL COMPLIANCE TEST:
    Verify that Croma adapter executes ZERO network calls,
    refuses scraping, and returns cache_policy=None.
    """
    url = "https://www.croma.com/apple-iphone-15/p/270412"
    result = adapter.scrape(url)

    # Assert zero network requests
    assert mock_get.call_count == 0
    assert mock_post.call_count == 0

    # Assert structured policy failure
    assert result.success is False
    assert result.site == "croma"
    assert result.source_category == SourceCategory.POLICY_RESTRICTED
    assert result.is_commercial_store is True
    assert result.cache_policy is None  # Strictly None, no dummy object
    assert "Terms of Use" in result.error
    assert "Section 12" in result.error

