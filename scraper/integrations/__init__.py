"""
Integrations package containing the five scraper adapters.
"""

from scraper.integrations.open_prices import OpenPricesAdapter
from scraper.integrations.local_store import LocalStoreAdapter
from scraper.integrations.amazon import AmazonCreatorsAdapter
from scraper.integrations.flipkart import FlipkartAffiliateAdapter
from scraper.integrations.croma import CromaPolicyAdapter

__all__ = [
    "OpenPricesAdapter",
    "LocalStoreAdapter",
    "AmazonCreatorsAdapter",
    "FlipkartAffiliateAdapter",
    "CromaPolicyAdapter",
]

