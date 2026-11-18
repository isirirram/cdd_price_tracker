"""
Integrations package containing scraper adapters for all supported e-commerce platforms.
"""

from scraper.integrations.open_prices import OpenPricesAdapter
from scraper.integrations.local_store import LocalStoreAdapter
from scraper.integrations.amazon import AmazonCreatorsAdapter
from scraper.integrations.flipkart import FlipkartAffiliateAdapter
from scraper.integrations.croma import CromaPolicyAdapter
from scraper.integrations.shopify import ShopifyAdapter
from scraper.integrations.woocommerce import WooCommerceAdapter
from scraper.integrations.bigcommerce import BigCommerceAdapter
from scraper.integrations.wix import WixAdapter
from scraper.integrations.prestashop import PrestaShopAdapter
from scraper.integrations.opencart import OpenCartAdapter
from scraper.integrations.generic import GenericEcommerceAdapter

__all__ = [
    "OpenPricesAdapter",
    "LocalStoreAdapter",
    "AmazonCreatorsAdapter",
    "FlipkartAffiliateAdapter",
    "CromaPolicyAdapter",
    "ShopifyAdapter",
    "WooCommerceAdapter",
    "BigCommerceAdapter",
    "WixAdapter",
    "PrestaShopAdapter",
    "OpenCartAdapter",
    "GenericEcommerceAdapter",
]
