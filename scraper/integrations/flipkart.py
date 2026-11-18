"""
Flipkart Affiliate API Adapter - Slot 4 (Credential-Gated Commercial Integration).

Implements the official Flipkart Affiliate API specification.
Handles FSN (Flipkart Serial Number) resolution and custom header authentication.
Enforces allow_historical_storage=False until partner contract permissions are verified.
"""

import logging
import re
from typing import Optional
import requests

from scraper.base_scraper import BaseScraper
from scraper.config import config
from scraper.models import CachePolicy, ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class FlipkartAffiliateAdapter(BaseScraper):
    """
    Adapter for Flipkart using the official Flipkart Affiliate REST API.

    Category: CREDENTIAL_GATED
    Commercial Store: True
    Cache Policy:
      - Price TTL: 86400 seconds (24-hour feed refresh)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: False (Conservative setting until contract verified)
    """

    SITE_NAME = "flipkart"
    BASE_API_URL = "https://affiliate-api.flipkart.net/affiliate/1.0/product.json"

    FSN_PATTERNS = [
        re.compile(r"[?&]pid=([a-zA-Z0-9]{16})", re.IGNORECASE),
        re.compile(r"/p/(itm[a-zA-Z0-9]{13,16})", re.IGNORECASE),
        re.compile(r"^fsn:([a-zA-Z0-9]{16})$", re.IGNORECASE),
        re.compile(r"^([a-zA-Z0-9]{16})$", re.IGNORECASE),
    ]

    def can_handle(self, url: str) -> bool:
        """Check if URL targets Flipkart or contains an explicit FSN."""
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()
        if "flipkart.com" in clean_url or "dl.flipkart.com" in clean_url or clean_url.startswith("fsn:"):
            return True
        return False

    def validate_url(self, url: str) -> bool:
        """Verify that a valid product ID or FSN can be extracted."""
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract the 16-character Flipkart Serial Number (FSN) or item ID."""
        if not url:
            return None
        clean_url = url.strip()
        for pattern in self.FSN_PATTERNS:
            match = pattern.search(clean_url)
            if match:
                return match.group(1)
        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Explicitly defines cache retention under conservative affiliate terms."""
        return CachePolicy(
            price_ttl_seconds=86400,        # 24-hour feed refresh
            metadata_ttl_seconds=86400,     # 24-hour metadata
            allow_historical_storage=False  # Gated until explicitly verified
        )

    def scrape(self, url: str) -> ScraperResult:
        """Query Flipkart Affiliate API if configured, or return credential-gated status."""
        product_id = self.extract_product_id(url)
        if not product_id:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error="Invalid Flipkart URL: Could not extract a valid 16-character product ID (pid/FSN).",
                cache_policy=self._get_cache_policy()
            )

        affiliate_id = config.flipkart_affiliate_id
        affiliate_token = config.flipkart_affiliate_token

        if not (affiliate_id and affiliate_token):
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=(
                    "Flipkart Affiliate API credentials missing. Set FLIPKART_AFFILIATE_ID and "
                    "FLIPKART_AFFILIATE_TOKEN in .env. Note: Public direct affiliate registrations are "
                    "currently suspended by Flipkart; legacy account credentials required."
                ),
                cache_policy=self._get_cache_policy(),
                attribution="Flipkart Affiliate Program"
            )

        headers = {
            "Fk-Affiliate-Id": affiliate_id,
            "Fk-Affiliate-Token": affiliate_token,
            "Accept": "application/json"
        }

        try:
            resp = requests.get(
                self.BASE_API_URL,
                params={"id": product_id},
                headers=headers,
                timeout=10
            )
            if resp.status_code == 404:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.CREDENTIAL_GATED,
                    is_commercial_store=True,
                    error=f"Product with ID '{product_id}' not found in Flipkart catalog.",
                    cache_policy=self._get_cache_policy()
                )
            if resp.status_code == 403 or resp.status_code == 401:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.CREDENTIAL_GATED,
                    is_commercial_store=True,
                    error="Flipkart API authentication failed. Check FLIPKART_AFFILIATE_ID and token validity.",
                    cache_policy=self._get_cache_policy()
                )
            resp.raise_for_status()
            data = resp.json()
            return self._parse_api_response(data, product_id, url)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error="Timeout connecting to Flipkart Affiliate API.",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"Flipkart Affiliate API exception: {e}")
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=f"Flipkart Affiliate API error: {str(e)}",
                cache_policy=self._get_cache_policy()
            )

    def _parse_api_response(self, data: dict, product_id: str, url: str) -> ScraperResult:
        """Parse official Flipkart Affiliate API product JSON."""
        base_info = data.get("productBaseInfoV1", {})
        title = base_info.get("title")

        price_obj = base_info.get("flipkartSellingPrice", {}) or base_info.get("maximumRetailPrice", {})
        raw_price = price_obj.get("amount")
        currency = price_obj.get("currency") or "INR"
        normalized_price = self.normalize_price(raw_price)

        if normalized_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=f"No valid selling price available for Flipkart item '{product_id}'.",
                cache_policy=self._get_cache_policy(),
                image_url=None
            )

        # Extract product image URL if present
        image_url = None
        image_urls = base_info.get("imageUrls")
        if isinstance(image_urls, dict):
            # Prefer higher resolution: 800x800, 400x400, 200x200, or first valid URL string
            for resolution in ("800x800", "400x400", "200x200"):
                val = image_urls.get(resolution)
                if isinstance(val, str) and (val.startswith("http://") or val.startswith("https://")):
                    image_url = val
                    break
            if not image_url:
                for val in image_urls.values():
                    if isinstance(val, str) and (val.startswith("http://") or val.startswith("https://")):
                        image_url = val
                        break
        elif isinstance(image_urls, list) and image_urls:
            first_val = image_urls[0]
            if isinstance(first_val, str) and (first_val.startswith("http://") or first_val.startswith("https://")):
                image_url = first_val
        elif isinstance(image_urls, str) and (image_urls.startswith("http://") or image_urls.startswith("https://")):
            image_url = image_urls

        return ScraperResult(
            success=True,
            product_name=title or f"Flipkart Product ({product_id})",
            current_price=normalized_price,
            currency=currency,
            image_url=image_url,
            site=self.SITE_NAME,
            product_url=url,
            source_category=SourceCategory.CREDENTIAL_GATED,
            is_commercial_store=True,
            error=None,
            cache_policy=self._get_cache_policy(),
            attribution="Product data sourced via official Flipkart Affiliate API."
        )

