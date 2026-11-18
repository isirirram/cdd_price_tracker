"""
Unit tests for ScraperFactory URL detection, adapter routing, and error boundaries.
"""

import pytest

from scraper.exceptions import InvalidUrlError, UnsupportedWebsiteError
from scraper.integrations import (
    AmazonCreatorsAdapter,
    BigCommerceAdapter,
    CromaPolicyAdapter,
    FlipkartAffiliateAdapter,
    GenericEcommerceAdapter,
    LocalStoreAdapter,
    OpenCartAdapter,
    OpenPricesAdapter,
    PrestaShopAdapter,
    ShopifyAdapter,
    WixAdapter,
    WooCommerceAdapter,
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


def test_factory_routes_shopify():
    """Verify Shopify URLs map to ShopifyAdapter."""
    assert isinstance(default_factory.get_adapter("https://store.myshopify.com/products/snowboard"), ShopifyAdapter)
    assert isinstance(default_factory.get_adapter("shopify://store.myshopify.com/products/snowboard"), ShopifyAdapter)


def test_factory_routes_woocommerce():
    """Verify WooCommerce URLs map to WooCommerceAdapter."""
    assert isinstance(default_factory.get_adapter("https://example.com/product/flying-ninja/"), WooCommerceAdapter)
    assert isinstance(default_factory.get_adapter("woocommerce://store.com/product/hoodie"), WooCommerceAdapter)


def test_factory_routes_bigcommerce():
    """Verify BigCommerce URLs map to BigCommerceAdapter."""
    assert isinstance(default_factory.get_adapter("https://store.mybigcommerce.com/products/sample-item"), BigCommerceAdapter)
    assert isinstance(default_factory.get_adapter("bigcommerce://store.com/products/sample"), BigCommerceAdapter)


def test_factory_routes_wix():
    """Verify Wix URLs map to WixAdapter."""
    assert isinstance(default_factory.get_adapter("https://store.wixsite.com/site/product-page/summer-dress"), WixAdapter)
    assert isinstance(default_factory.get_adapter("wix://site.com/product-page/dress"), WixAdapter)


def test_factory_routes_prestashop():
    """Verify PrestaShop URLs map to PrestaShopAdapter."""
    assert isinstance(default_factory.get_adapter("https://store.com/12-printed-summer-dress.html"), PrestaShopAdapter)
    assert isinstance(default_factory.get_adapter("prestashop://store.com/12-dress.html"), PrestaShopAdapter)


def test_factory_routes_opencart():
    """Verify OpenCart URLs map to OpenCartAdapter."""
    assert isinstance(default_factory.get_adapter("https://store.com/index.php?route=product/product&product_id=42"), OpenCartAdapter)
    assert isinstance(default_factory.get_adapter("opencart://store.com/item?product_id=99"), OpenCartAdapter)


def test_factory_routes_generic():
    """Verify arbitrary shopping website URLs fallback to GenericEcommerceAdapter."""
    assert isinstance(default_factory.get_adapter("https://www.yeti.com/drinkware/tumblers/21071509045.html"), GenericEcommerceAdapter)
    assert isinstance(default_factory.get_adapter("https://shop.nordstrom.com/s/cashmere-sweater/567890"), GenericEcommerceAdapter)



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

