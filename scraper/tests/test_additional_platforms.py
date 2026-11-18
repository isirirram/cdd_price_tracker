"""
Unit and contract tests for Priority 2 platforms: Wix, PrestaShop, and OpenCart.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from scraper.integrations.opencart import OpenCartAdapter
from scraper.integrations.prestashop import PrestaShopAdapter
from scraper.integrations.wix import WixAdapter
from scraper.models import SourceCategory

FIXTURES_DIR = Path(__file__).parent / "benchmark" / "fixtures"


# ==============================================================================
# WIX TESTS
# ==============================================================================

@pytest.fixture
def wix_adapter():
    return WixAdapter()


def test_wix_can_handle(wix_adapter):
    """Verify Wix URL detection."""
    assert wix_adapter.can_handle("https://store.wixsite.com/boutique/product-page/leather-handbag")
    assert wix_adapter.can_handle("wix://my-store.com/product-page/summer-dress")
    assert not wix_adapter.can_handle("https://amazon.in/dp/B08L5W4SW6")


def test_wix_extract_product_id(wix_adapter):
    """Verify Wix slug extraction."""
    assert wix_adapter.extract_product_id(
        "https://store.wixsite.com/boutique/product-page/leather-handbag"
    ) == "leather-handbag"


@patch("scraper.security.safe_get")
def test_wix_successful_mock_scrape(mock_safe_get, wix_adapter):
    """Verify parsing of Wix storefront HTML/JSON-LD fixture."""
    fixture_path = FIXTURES_DIR / "wix_sample.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content
    mock_safe_get.return_value = mock_resp

    url = "https://store.wixsite.com/boutique/product-page/leather-handbag"
    result = wix_adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "Handcrafted Leather Handbag"
    assert result.current_price == 4299.0
    assert result.currency == "INR"
    assert "sample_bag.jpg" in result.image_url
    assert result.site == "wix"
    assert result.source_category == SourceCategory.PUBLIC_STORE_API


@patch("scraper.security.safe_get")
def test_wix_authentication_required_handling(mock_safe_get, wix_adapter):
    """Verify clear error when Wix store requires login/membership (HTTP 401/403)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_safe_get.return_value = mock_resp

    result = wix_adapter.scrape("https://store.wixsite.com/members-only/product-page/vip-item")
    assert result.success is False
    assert "authentication" in result.error.lower() or "login" in result.error.lower()


# ==============================================================================
# PRESTASHOP TESTS
# ==============================================================================

@pytest.fixture
def prestashop_adapter():
    return PrestaShopAdapter()


def test_prestashop_can_handle(prestashop_adapter):
    """Verify PrestaShop URL detection."""
    assert prestashop_adapter.can_handle("https://prestashop.example.com/12-printed-summer-dress.html")
    assert prestashop_adapter.can_handle("https://store.com/index.php?id_product=12&controller=product")
    assert prestashop_adapter.can_handle("prestashop://store.com/12-dress.html")
    assert not prestashop_adapter.can_handle("https://flipkart.com/item")


def test_prestashop_extract_product_id(prestashop_adapter):
    """Verify PrestaShop product ID extraction."""
    assert prestashop_adapter.extract_product_id(
        "https://prestashop.example.com/12-printed-summer-dress.html"
    ) == "12"
    assert prestashop_adapter.extract_product_id(
        "https://store.com/index.php?id_product=45&controller=product"
    ) == "45"


@patch("scraper.security.safe_get")
def test_prestashop_successful_mock_scrape(mock_safe_get, prestashop_adapter):
    """Verify parsing of PrestaShop storefront HTML/JSON-LD fixture."""
    fixture_path = FIXTURES_DIR / "prestashop_sample.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content
    mock_safe_get.return_value = mock_resp

    url = "https://prestashop.example.com/12-printed-summer-dress.html"
    result = prestashop_adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "Printed Summer Dress"
    assert result.current_price == 1899.0
    assert result.currency == "INR"
    assert "12.jpg" in result.image_url
    assert result.site == "prestashop"
    assert result.source_category == SourceCategory.PUBLIC_STORE_API


@patch("scraper.security.safe_get")
def test_prestashop_protected_api_handling(mock_safe_get, prestashop_adapter):
    """Verify clear error when PrestaShop Web Service requires API key (HTTP 401)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_safe_get.return_value = mock_resp

    result = prestashop_adapter.scrape("https://prestashop.example.com/12-item.html")
    assert result.success is False
    assert "authentication" in result.error.lower() or "api key" in result.error.lower()


# ==============================================================================
# OPENCART TESTS
# ==============================================================================

@pytest.fixture
def opencart_adapter():
    return OpenCartAdapter()


def test_opencart_can_handle(opencart_adapter):
    """Verify OpenCart URL detection."""
    assert opencart_adapter.can_handle("https://opencart.example.com/index.php?route=product/product&product_id=42")
    assert opencart_adapter.can_handle("opencart://store.com/item?product_id=99")
    assert not opencart_adapter.can_handle("https://croma.com/p/12345")


def test_opencart_extract_product_id(opencart_adapter):
    """Verify OpenCart product ID extraction."""
    assert opencart_adapter.extract_product_id(
        "https://opencart.example.com/index.php?route=product/product&product_id=42"
    ) == "42"


@patch("scraper.security.safe_get")
def test_opencart_successful_mock_scrape(mock_safe_get, opencart_adapter):
    """Verify parsing of OpenCart storefront HTML/JSON-LD fixture."""
    fixture_path = FIXTURES_DIR / "opencart_sample.html"
    with open(fixture_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content
    mock_safe_get.return_value = mock_resp

    url = "https://opencart.example.com/index.php?route=product/product&product_id=42"
    result = opencart_adapter.scrape(url)

    assert result.success is True
    assert result.product_name == "iPhone 15 Pro Max"
    assert result.current_price == 134900.0
    assert result.currency == "INR"
    assert "iphone-500x500.jpg" in result.image_url
    assert result.site == "opencart"
    assert result.source_category == SourceCategory.PUBLIC_STORE_API


@patch("scraper.security.safe_get")
def test_opencart_maintenance_mode_handling(mock_safe_get, opencart_adapter):
    """Verify handling when OpenCart store is maintenance-gated or requires login."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_safe_get.return_value = mock_resp

    result = opencart_adapter.scrape("https://opencart.example.com/index.php?route=product/product&product_id=42")
    assert result.success is False
    assert "private" in result.error.lower() or "restricted" in result.error.lower()
