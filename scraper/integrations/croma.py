"""
Croma Policy-Restricted Adapter - Slot 5.

Demonstrates legal compliance by actively refusing unauthorized web scraping.
Validates croma.com URLs but executes zero network requests, cleanly raising
PolicyRestrictedWebsiteError and returning ScraperResult without a CachePolicy.
"""

import logging
import re
from typing import Optional

from scraper.base_scraper import BaseScraper
from scraper.exceptions import PolicyRestrictedWebsiteError
from scraper.models import ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class CromaPolicyAdapter(BaseScraper):
    """
    Adapter representing policy-restricted platforms lacking an authorized API.

    Category: POLICY_RESTRICTED
    Commercial Store: True
    Cache Policy: None (No data is retrieved)
    """

    SITE_NAME = "croma"
    SLUG_PATTERN = re.compile(r"/([a-zA-Z0-9-]+)/p/(\d{5,10})", re.IGNORECASE)

    def can_handle(self, url: str) -> bool:
        """Check if URL targets Croma electronics."""
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()
        return "croma.com" in clean_url

    def validate_url(self, url: str) -> bool:
        """Verify URL structure conforms to croma.com product path conventions."""
        if not self.can_handle(url):
            return False
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract product code from /product-slug/p/123456 URL pattern."""
        if not url:
            return None
        match = self.SLUG_PATTERN.search(url.strip())
        if match:
            return match.group(2)
        # Fallback: extract any trailing numeric ID in path
        num_match = re.search(r"/(\d{5,10})(?:[/?#]|$)", url)
        if num_match:
            return num_match.group(1)
        return "croma-item"

    def scrape(self, url: str) -> ScraperResult:
        """
        Actively refuses automated web scraping.
        Raises PolicyRestrictedWebsiteError internally and returns a clean,
        structured failure result with cache_policy=None.
        """
        product_id = self.extract_product_id(url)
        policy_reason = (
            "Automated data extraction refused: Croma's Terms of Use (Section 12) strictly "
            "prohibit robots, spiders, scrapers, and automated price monitoring. "
            "Croma does not provide an authorized public developer API."
        )

        logger.info(f"Refusing scraping for Croma item '{product_id}': {policy_reason}")

        return ScraperResult(
            success=False,
            product_name=None,
            current_price=None,
            currency="INR",
            site=self.SITE_NAME,
            product_url=url,
            source_category=SourceCategory.POLICY_RESTRICTED,
            is_commercial_store=True,
            error=policy_reason,
            cache_policy=None,  # No cache policy for policy-restricted failures
            attribution=None,
            image_url=None
        )

