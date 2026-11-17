"""
Unit tests for ScraperFactory URL detection, adapter routing, and error boundaries.
"""

import pytest

from scraper.exceptions import InvalidUrlError, UnsupportedWebsiteError
from scraper.integrations import (
    AmazonCreatorsAdapter,
    CromaPolicyAdapter,
    FlipkartAffiliateAdapter,
    LocalStoreAdapter,
    OpenPricesAdapter,
)
from scraper.models import SourceCategory
from scraper.scraper_factory import ScraperFactory, default_factory, scrape_product


def test_factory_routes_open_prices():
    """Verify Open Prices URLs and barcodes map to OpenPricesAdapter."""
    assert isinstance(default_factory.get_adapter("https://in.openfoodfacts.org/product/8901030825347"), OpenPricesAdapter)
    assert isinstance(default_factory.get_adapter("barcode:8901030825347"), OpenPricesAdapter)
    assert isinstance(default_factory.get_adapter("8901030825347"), OpenPricesAdapter)


def test_factory_routes_local_store():
    """Verify localstore URLs map to LocalStoreAdapter."""
    assert isinstance(default_factory.get_adapter("http://127.0.0.1:8000/products/product-001"), LocalStoreAdapter)
    assert isinstance(default_factory.get_adapter("localstore://product-001"), LocalStoreAdapter)


def test_factory_routes_amazon():
    """Verify Amazon India URLs map to AmazonCreatorsAdapter."""
    assert isinstance(default_factory.get_adapter("https://www.amazon.in/dp/B08L5W4SW6"), AmazonCreatorsAdapter)
    assert isinstance(default_factory.get_adapter("https://amzn.in/d/sample"), AmazonCreatorsAdapter)


def test_factory_routes_flipkart():
    """Verify Flipkart URLs map to FlipkartAffiliateAdapter."""
    assert isinstance(default_factory.get_adapter("https://www.flipkart.com/product/p/itm1234567890123"), FlipkartAffiliateAdapter)
    assert isinstance(default_factory.get_adapter("https://dl.flipkart.com/dl/item?pid=MOB1234567890123"), FlipkartAffiliateAdapter)


def test_factory_routes_croma():
    """Verify Croma URLs map to CromaPolicyAdapter."""
    assert isinstance(default_factory.get_adapter("https://www.croma.com/sample/p/123456"), CromaPolicyAdapter)


def test_factory_unsupported_website():
    """Verify unsupported websites raise UnsupportedWebsiteError."""
    with pytest.raises(UnsupportedWebsiteError):
        default_factory.get_adapter("https://myntra.com/product/1234")

    with pytest.raises(UnsupportedWebsiteError):
        default_factory.get_adapter("https://ajio.com/product/1234")


def test_scrape_product_empty_input_returns_failure():
    """Verify public facade converts empty/None inputs into clean ScraperResult."""
    res1 = scrape_product("")
    assert res1.success is False
    assert "empty" in res1.error.lower()

    res2 = scrape_product(None)
    assert res2.success is False
    assert "empty" in res2.error.lower()


def test_scrape_product_unsupported_website_returns_failure():
    """Verify public facade returns clean failure for unsupported websites."""
    res = scrape_product("https://myntra.com/shoes/p/999")
    assert res.success is False
    assert "not supported" in res.error.lower()
    assert res.source_category == SourceCategory.POLICY_RESTRICTED

