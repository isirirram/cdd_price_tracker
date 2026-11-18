"""
BigCommerce Storefront Adapter - Slot 8.

Extracts live product titles, current prices, currencies, and image URLs
using BigCommerce storefront structured data (Schema.org JSON-LD) and Stencil microdata.
Gracefully handles stores requiring authentication or private API credentials.
Enforces SSRF protection against private networks.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

import requests

from scraper import security
from scraper.base_scraper import BaseScraper
from scraper.exceptions import InvalidUrlError
from scraper.models import CachePolicy, ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class BigCommerceAdapter(BaseScraper):
    """
    Adapter for BigCommerce stores using public storefront structured data.

    Category: PUBLIC_STORE_API
    Commercial Store: True
    Cache Policy:
      - Price TTL: 3600 seconds (1 hour)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: True
    """

    SITE_NAME = "bigcommerce"
    SLUG_PATTERN = re.compile(
        r"/(?:products/)?([a-zA-Z0-9_-]+)(?:\.html)?(?:[/?#]|$)",
        re.IGNORECASE
    )

    def can_handle(self, url: str) -> bool:
        """
        Check if URL targets a BigCommerce store.
        Matches *.mybigcommerce.com, bigcommerce: URIs, or domain containing 'bigcommerce'.
        """
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()

        if clean_url.startswith("bigcommerce:") or clean_url.startswith("bigcommerce://"):
            return True
        if "mybigcommerce.com" in clean_url or "bigcommerce" in clean_url:
            return True

        return False

    def validate_url(self, url: str) -> bool:
        """Verify URL structure conforms to BigCommerce product conventions."""
        if not self.can_handle(url):
            return False
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the BigCommerce product slug or filename from the URL.
        Example: /products/sample-item.html -> 'sample-item'
        """
        if not url:
            return None
        clean_url = url.strip()

        # Handle bigcommerce:// or bigcommerce: URIs
        if clean_url.startswith("bigcommerce://"):
            clean_url = "https://" + clean_url[len("bigcommerce://"):]
        elif clean_url.startswith("bigcommerce:"):
            clean_url = "https://" + clean_url[len("bigcommerce:"):]

        try:
            parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
            match = self.SLUG_PATTERN.search(parsed.path)
            if match:
                slug = match.group(1).lower()
                if slug not in ("products", "cart", "checkout", "login", "account"):
                    return slug
        except Exception:
            pass

        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Return standardized cache policy for BigCommerce public endpoints."""
        return CachePolicy(
            price_ttl_seconds=3600,         # 1-hour price cache
            metadata_ttl_seconds=86400,     # 24-hour metadata
            allow_historical_storage=True   # Permitted for public storefront data
        )

    def scrape(self, url: str) -> ScraperResult:
        """
        Retrieve live product data from BigCommerce storefront page via public structured data.
        """
        clean_url = url.strip()

        # Normalize bigcommerce: schemes for HTTP resolution
        http_url = clean_url
        if http_url.startswith("bigcommerce://"):
            http_url = "https://" + http_url[len("bigcommerce://"):]
        elif http_url.startswith("bigcommerce:"):
            http_url = "https://" + http_url[len("bigcommerce:"):]
        elif not (http_url.startswith("http://") or http_url.startswith("https://")):
            http_url = f"https://{http_url}"

        # 1. SSRF and Domain Security Validation
        try:
            validated_url = security.validate_safe_url(http_url)
        except InvalidUrlError as e:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Security rejection: {e.message}",
                cache_policy=self._get_cache_policy()
            )

        # 2. Extract Product Slug
        slug = self.extract_product_id(validated_url)
        if not slug:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error="Invalid BigCommerce URL: Could not extract valid product slug.",
                cache_policy=self._get_cache_policy()
            )

        parsed = urlparse(validated_url)
        domain = parsed.netloc

        # 3. Query BigCommerce Public Storefront Page
        try:
            resp = security.safe_get(
                validated_url,
                headers={"Accept": "text/html,application/xhtml+xml,application/json"},
                timeout=10
            )

            if resp.status_code == 404:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=f"Product '{slug}' was not found on BigCommerce store '{domain}' (HTTP 404).",
                    cache_policy=self._get_cache_policy()
                )

            if resp.status_code in (401, 403):
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=(
                        f"BigCommerce store '{domain}' requires authentication or private API credentials "
                        f"to access catalog data (HTTP {resp.status_code})."
                    ),
                    cache_policy=self._get_cache_policy()
                )

            resp.raise_for_status()
            html_text = resp.text

            return self._parse_bigcommerce_content(html_text, slug, url, domain)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Connection timed out while querying BigCommerce store '{domain}'.",
                cache_policy=self._get_cache_policy()
            )
        except requests.RequestException as e:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Network error querying BigCommerce store: {str(e)}",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"BigCommerce extraction error: {e}", exc_info=True)
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Failed to extract BigCommerce product data: {str(e)}",
                cache_policy=self._get_cache_policy()
            )

    def _parse_bigcommerce_content(
        self,
        html_text: str,
        slug: str,
        original_url: str,
        domain: str
    ) -> ScraperResult:
        """Parse BigCommerce public HTML/JSON-LD into standard ScraperResult."""
        # 1. Look for Schema.org JSON-LD Product blocks
        json_ld_nodes = security.extract_json_ld(html_text)
        product_node = security.find_product_in_json_ld(json_ld_nodes)

        title = None
        raw_price = None
        currency = "INR"
        image_url = None

        if product_node:
            title = product_node.get("name")
            # Offers could be a dict or list
            offers = product_node.get("offers")
            offer_dict = None
            if isinstance(offers, dict):
                offer_dict = offers
            elif isinstance(offers, list) and offers:
                offer_dict = offers[0] if isinstance(offers[0], dict) else None

            if offer_dict:
                raw_price = offer_dict.get("price") or offer_dict.get("lowPrice")
                currency = offer_dict.get("priceCurrency") or currency

            # Image
            img = product_node.get("image")
            if isinstance(img, str):
                image_url = img
            elif isinstance(img, list) and img:
                image_url = img[0] if isinstance(img[0], str) else None
            elif isinstance(img, dict):
                image_url = img.get("url")

        # 2. Fallback to OpenGraph and Meta tags if JSON-LD is missing
        if not title:
            og_title = re.search(r'<meta[^>]*property=[\'"]og:title[\'"][^>]*content=[\'"](.*?)[\'"]', html_text, re.IGNORECASE)
            if og_title:
                title = og_title.group(1).strip()

        if raw_price is None:
            price_meta = re.search(
                r'<meta[^>]*property=[\'"]product:price:amount[\'"][^>]*content=[\'"](.*?)[\'"]',
                html_text,
                re.IGNORECASE
            )
            if price_meta:
                raw_price = price_meta.group(1).strip()

        if not currency or currency == "INR":
            cur_meta = re.search(
                r'<meta[^>]*property=[\'"]product:price:currency[\'"][^>]*content=[\'"](.*?)[\'"]',
                html_text,
                re.IGNORECASE
            )
            if cur_meta:
                currency = cur_meta.group(1).strip().upper()

        if not image_url:
            og_img = re.search(r'<meta[^>]*property=[\'"]og:image[\'"][^>]*content=[\'"](.*?)[\'"]', html_text, re.IGNORECASE)
            if og_img:
                image_url = og_img.group(1).strip()

        # Validate extracted fields
        normalized_price = self.normalize_price(raw_price)
        if normalized_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=original_url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"No valid public price found on BigCommerce page for '{slug}'.",
                cache_policy=self._get_cache_policy()
            )

        if not title:
            title = f"BigCommerce Product ({slug})"

        if image_url and not (image_url.startswith("http://") or image_url.startswith("https://")):
            image_url = None

        return ScraperResult(
            success=True,
            product_name=title,
            current_price=normalized_price,
            currency=currency or "INR",
            image_url=image_url,
            site=self.SITE_NAME,
            product_url=original_url,
            source_category=SourceCategory.PUBLIC_STORE_API,
            is_commercial_store=True,
            error=None,
            cache_policy=self._get_cache_policy(),
            attribution="Product data sourced via BigCommerce public storefront."
        )
