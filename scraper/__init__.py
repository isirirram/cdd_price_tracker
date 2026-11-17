"""
Smart Price Tracker - Scraper and Price Extraction Module (Person 2).

Provides standardized, authorized product name and price extraction
across supported data sources for Person 3's Celery worker and scheduler.
"""

from scraper.base_scraper import BaseScraper
from scraper.exceptions import (
    ApiCredentialsMissingError,
    InvalidUrlError,
    NetworkTimeoutError,
    PolicyRestrictedWebsiteError,
    PriceNotFoundError,
    ProductNotFoundError,
    RegistrationGatedError,
    ScraperException,
    UnsupportedWebsiteError,
)
from scraper.models import CachePolicy, ScraperResult, SourceCategory
from scraper.scraper_factory import ScraperFactory, default_factory, scrape_product

__all__ = [
    "scrape_product",
    "ScraperResult",
    "SourceCategory",
    "CachePolicy",
    "ScraperFactory",
    "default_factory",
    "BaseScraper",
    "ScraperException",
    "InvalidUrlError",
    "UnsupportedWebsiteError",
    "ApiCredentialsMissingError",
    "RegistrationGatedError",
    "PolicyRestrictedWebsiteError",
    "NetworkTimeoutError",
    "ProductNotFoundError",
    "PriceNotFoundError",
]

