"""
Scraper Factory and universal entry point facade.

Inspects incoming URLs, selects the matching adapter, enforces error boundaries,
and returns a guaranteed ScraperResult.
"""

import logging
from typing import List, Optional
from urllib.parse import urlparse

from scraper.base_scraper import BaseScraper
from scraper.exceptions import (
    InvalidUrlError,
    ScraperException,
    UnsupportedWebsiteError,
)
from scraper.integrations import (
    AmazonCreatorsAdapter,
    CromaPolicyAdapter,
    FlipkartAffiliateAdapter,
    LocalStoreAdapter,
    OpenPricesAdapter,
)
from scraper.models import ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Registry and router for all supported product extraction adapters."""

    def __init__(self, adapters: Optional[List[BaseScraper]] = None):
        self._adapters: List[BaseScraper] = adapters or [
            OpenPricesAdapter(),
            LocalStoreAdapter(),
            AmazonCreatorsAdapter(),
            FlipkartAffiliateAdapter(),
            CromaPolicyAdapter(),
        ]

    def register_adapter(self, adapter: BaseScraper) -> None:
        """Register a new adapter dynamically."""
        self._adapters.append(adapter)

    def get_adapter(self, url: str) -> BaseScraper:
        """
        Identify the target website and return the appropriate adapter.

        Raises:
            InvalidUrlError: If url is empty or not a string.
            UnsupportedWebsiteError: If no registered adapter can handle the domain.
        """
        if not url or not isinstance(url, str):
            raise InvalidUrlError("URL cannot be empty or non-string.", site="unknown")

        clean_url = url.strip()
        for adapter in self._adapters:
            if adapter.can_handle(clean_url):
                return adapter

        # Extract domain name for a helpful error message
        domain = "unknown"
        try:
            parsed = urlparse(clean_url)
            domain = parsed.netloc or clean_url.split("/")[0]
        except Exception:
            pass

        raise UnsupportedWebsiteError(
            f"The website '{domain}' is not supported. Supported sources are: "
            "Open Prices (openfoodfacts.org, barcode:*), LocalStore (127.0.0.1:8000), "
            "Amazon India (amazon.in), Flipkart (flipkart.com), and Croma (croma.com).",
            site=domain
        )


# Singleton factory instance
default_factory = ScraperFactory()


def scrape_product(product_url: str, factory: Optional[ScraperFactory] = None) -> ScraperResult:
    """
    Public entry point for Person 3 (Worker/Scheduler) and callers.

    Guaranteed behavior:
    1. Validates the product URL.
    2. Dispatches to the correct adapter.
    3. Normalizes prices into numeric floats in INR.
    4. Never crashes; unhandled exceptions are caught and returned as failure results.
    """
    active_factory = factory or default_factory

    if not product_url or not isinstance(product_url, str) or not product_url.strip():
        return ScraperResult(
            success=False,
            site="unknown",
            product_url=str(product_url) if product_url else "",
            source_category=SourceCategory.POLICY_RESTRICTED,
            is_commercial_store=False,
            error="Invalid input: Product URL cannot be empty.",
            cache_policy=None
        )

    clean_url = product_url.strip()

    try:
        adapter = active_factory.get_adapter(clean_url)
        return adapter.scrape(clean_url)
    except UnsupportedWebsiteError as e:
        logger.warning(f"Unsupported website requested: {e.message}")
        return ScraperResult(
            success=False,
            site=e.site,
            product_url=clean_url,
            source_category=SourceCategory.POLICY_RESTRICTED,
            is_commercial_store=False,
            error=e.message,
            cache_policy=None
        )
    except InvalidUrlError as e:
        return ScraperResult(
            success=False,
            site="unknown",
            product_url=clean_url,
            source_category=SourceCategory.POLICY_RESTRICTED,
            is_commercial_store=False,
            error=e.message,
            cache_policy=None
        )
    except Exception as e:
        logger.error(f"Unexpected fatal error during scraping for '{clean_url}': {e}", exc_info=True)
        return ScraperResult(
            success=False,
            site="unknown",
            product_url=clean_url,
            source_category=SourceCategory.POLICY_RESTRICTED,
            is_commercial_store=False,
            error=f"Unexpected internal scraper error: {str(e)}",
            cache_policy=None
        )

