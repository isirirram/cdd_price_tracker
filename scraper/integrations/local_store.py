"""
LocalStore Adapter - Slot 2 (Controlled Demonstration Storefront).

Connects to the self-contained local demonstration server (127.0.0.1:8000).
Enables deterministic live price drop simulation and image extraction for project evaluation.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse
import requests

from scraper.base_scraper import BaseScraper
from scraper.config import config
from scraper.models import CachePolicy, ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class LocalStoreAdapter(BaseScraper):
    """
    Adapter for querying the controlled demonstration storefront.

    Category: CONTROLLED_DEMO_STORE
    Commercial Store: False
    Historical Storage: True (Permitted on self-hosted demo store)
    """

    SITE_NAME = "local_store"
    ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

    def can_handle(self, url: str) -> bool:
        """Check if URL points to local demo storefront."""
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()
        if clean_url.startswith("localstore://"):
            return True
        try:
            parsed = urlparse(clean_url)
            netloc = parsed.netloc.split(":")[0]
            if netloc in ("127.0.0.1", "localhost") and "/products/" in parsed.path:
                return True
        except Exception:
            pass
        return False

    def validate_url(self, url: str) -> bool:
        """Verify that a valid product ID can be extracted from the URL."""
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract product ID (e.g. 'product-001') from the URL or localstore URI."""
        if not url:
            return None
        clean_url = url.strip()
        if clean_url.lower().startswith("localstore://"):
            pid = clean_url[13:].strip().split("/")[0].split("?")[0]
            return pid if self.ID_PATTERN.match(pid) else None

        try:
            parsed = urlparse(clean_url)
            match = re.search(r"/products/([a-zA-Z0-9_-]{1,64})", parsed.path)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Cache policy for local demonstration storefront."""
        return CachePolicy(
            price_ttl_seconds=60,           # Fast 1-minute refresh for dynamic demos
            metadata_ttl_seconds=86400,     # 24-hour metadata
            allow_historical_storage=True   # Permitted for demonstration store
        )

    def scrape(self, url: str) -> ScraperResult:
        """Query the local demonstration store and return ScraperResult with image URL."""
        product_id = self.extract_product_id(url)
        if not product_id:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CONTROLLED_DEMO_STORE,
                is_commercial_store=False,
                error="Invalid LocalStore URL: A valid product ID (alphanumeric, hyphens) could not be extracted.",
                cache_policy=None,
                image_url=None
            )

        base_url = config.local_store_url
        endpoint = f"{base_url}/products/{product_id}"

        try:
            resp = requests.get(endpoint, timeout=5)
            if resp.status_code == 404:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.CONTROLLED_DEMO_STORE,
                    is_commercial_store=False,
                    error=f"Product with ID '{product_id}' not found in LocalStore demonstration catalog.",
                    cache_policy=self._get_cache_policy(),
                    image_url=None
                )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CONTROLLED_DEMO_STORE,
                is_commercial_store=False,
                error=(
                    f"Local demonstration store is offline at {base_url}. "
                    "Start it using: python scraper/demo_store/server.py --port 8000"
                ),
                cache_policy=None,
                image_url=None
            )
        except requests.exceptions.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CONTROLLED_DEMO_STORE,
                is_commercial_store=False,
                error="Timeout connecting to LocalStore demonstration server.",
                cache_policy=None,
                image_url=None
            )
        except Exception as e:
            logger.error(f"Error querying LocalStore: {e}")
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CONTROLLED_DEMO_STORE,
                is_commercial_store=False,
                error=f"LocalStore API error: {str(e)}",
                cache_policy=None,
                image_url=None
            )

        title = data.get("title") or f"Demo Product ({product_id})"
        raw_price = data.get("price")
        currency = data.get("currency", "INR")
        image_url = data.get("image_url")
        normalized_price = self.normalize_price(raw_price)

        if normalized_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CONTROLLED_DEMO_STORE,
                is_commercial_store=False,
                error=f"LocalStore response for '{product_id}' contained no valid numeric price.",
                cache_policy=self._get_cache_policy(),
                image_url=None
            )

        return ScraperResult(
            success=True,
            product_name=title,
            current_price=normalized_price,
            currency=currency,
            image_url=image_url if (image_url and (image_url.startswith("http://") or image_url.startswith("https://"))) else None,
            site=self.SITE_NAME,
            product_url=url,
            source_category=SourceCategory.CONTROLLED_DEMO_STORE,
            is_commercial_store=False,
            error=None,
            cache_policy=self._get_cache_policy(),
            attribution="Sourced from Controlled Demonstration Storefront for System Evaluation"
        )
