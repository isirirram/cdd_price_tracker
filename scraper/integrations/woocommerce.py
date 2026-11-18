"""
WooCommerce Store API Adapter - Slot 7.

Extracts live product titles, current prices, currencies, and image URLs
using the official public WooCommerce Store API (/wp-json/wc/store/v1/products).
Handles currency minor unit conversions and graceful degradation when the Store API
is disabled or restricted.
Enforces SSRF protection against private networks.
"""

import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests

from scraper import security
from scraper.base_scraper import BaseScraper
from scraper.exceptions import InvalidUrlError
from scraper.models import CachePolicy, ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class WooCommerceAdapter(BaseScraper):
    """
    Adapter for WooCommerce stores using the public WooCommerce Store API.

    Category: PUBLIC_STORE_API
    Commercial Store: True
    Cache Policy:
      - Price TTL: 3600 seconds (1 hour)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: True
    """

    SITE_NAME = "woocommerce"
    SLUG_PATTERN = re.compile(
        r"/product/([a-zA-Z0-9_-]+)(?:[/?#]|$)",
        re.IGNORECASE
    )
    EXCLUDED_DOMAINS = {
        "myntra.com",
        "ajio.com",
        "tatacliq.com",
        "nykaa.com",
        "amazon.in",
        "amazon.com",
        "flipkart.com",
        "croma.com",
        "openfoodfacts.org",
        "dummyjson.com",
        "mybigcommerce.com",
        "bigcommerce.com",
        "wixsite.com",
        "wix.com",
        "prestashop.com",
        "opencart.com",
    }

    def can_handle(self, url: str) -> bool:
        """
        Check if URL targets a WooCommerce store.
        Matches woocommerce: URIs, domains containing 'woocommerce',
        or standard WooCommerce product paths (/product/{slug} - singular).
        """
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()

        if clean_url.startswith("woocommerce:") or clean_url.startswith("woocommerce://"):
            return True

        # Do not match URLs explicitly designated for other platform schemes
        if any(clean_url.startswith(p) for p in ("shopify:", "bigcommerce:", "wix:", "prestashop:", "opencart:")):
            return False

        try:
            parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
            domain = parsed.netloc or ""
            if any(ex in domain for ex in self.EXCLUDED_DOMAINS):
                return False
            if "woocommerce" in domain:
                return True
            if self.SLUG_PATTERN.search(parsed.path):
                return True
            query_params = parse_qs(parsed.query)
            if "product" in query_params or "post_type=product" in clean_url:
                return True
        except Exception:
            pass

        return False

    def validate_url(self, url: str) -> bool:
        """Verify URL structure conforms to WooCommerce product conventions."""
        if not self.can_handle(url):
            return False
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the WooCommerce product slug or numeric ID.
        Example: /product/flying-ninja/ -> 'flying-ninja'
        Example: /?product=123 -> '123'
        """
        if not url:
            return None
        clean_url = url.strip()

        # Handle woocommerce:// or woocommerce: URIs
        if clean_url.startswith("woocommerce://"):
            clean_url = "https://" + clean_url[len("woocommerce://"):]
        elif clean_url.startswith("woocommerce:"):
            clean_url = "https://" + clean_url[len("woocommerce:"):]

        try:
            parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
            match = self.SLUG_PATTERN.search(parsed.path)
            if match:
                return match.group(1).lower()

            # Check query parameters
            query_params = parse_qs(parsed.query)
            if "product" in query_params and query_params["product"]:
                return query_params["product"][0].strip()
            if "p" in query_params and query_params["p"]:
                return query_params["p"][0].strip()
        except Exception:
            pass

        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Return standardized cache policy for public WooCommerce endpoints."""
        return CachePolicy(
            price_ttl_seconds=3600,         # 1-hour price cache
            metadata_ttl_seconds=86400,     # 24-hour metadata
            allow_historical_storage=True   # Permitted for public storefront data
        )

    def scrape(self, url: str) -> ScraperResult:
        """
        Retrieve live product data from WooCommerce store via WooCommerce Store API.
        """
        clean_url = url.strip()

        # Normalize woocommerce: schemes for HTTP resolution
        http_url = clean_url
        if http_url.startswith("woocommerce://"):
            http_url = "https://" + http_url[len("woocommerce://"):]
        elif http_url.startswith("woocommerce:"):
            http_url = "https://" + http_url[len("woocommerce:"):]
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

        # 2. Extract Product Identifier (slug or ID)
        identifier = self.extract_product_id(validated_url)
        if not identifier:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error="Invalid WooCommerce URL: Could not extract product slug (/product/{slug}).",
                cache_policy=self._get_cache_policy()
            )

        parsed = urlparse(validated_url)
        domain = parsed.netloc
        scheme = parsed.scheme or "https"

        # Determine endpoint: numeric ID vs slug query
        if identifier.isdigit():
            endpoint = f"{scheme}://{domain}/wp-json/wc/store/v1/products/{identifier}"
        else:
            endpoint = f"{scheme}://{domain}/wp-json/wc/store/v1/products?slug={identifier}"

        # 3. Query WooCommerce Store API Endpoint
        try:
            resp = security.safe_get(
                endpoint,
                headers={"Accept": "application/json"},
                timeout=10
            )

            if resp.status_code == 404:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=f"Product '{identifier}' was not found on WooCommerce store '{domain}' (HTTP 404).",
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
                        f"WooCommerce Store API is disabled, blocked, or requires authentication on '{domain}' "
                        f"(HTTP {resp.status_code})."
                    ),
                    cache_policy=self._get_cache_policy()
                )

            resp.raise_for_status()
            data = resp.json()

            return self._parse_woocommerce_data(data, identifier, url, domain)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Connection timed out while querying WooCommerce store '{domain}'.",
                cache_policy=self._get_cache_policy()
            )
        except requests.RequestException as e:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Network error querying WooCommerce Store API: {str(e)}",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"WooCommerce extraction error: {e}", exc_info=True)
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Failed to extract WooCommerce product data: {str(e)}",
                cache_policy=self._get_cache_policy()
            )

    def _parse_woocommerce_data(
        self,
        data: any,
        identifier: str,
        original_url: str,
        domain: str
    ) -> ScraperResult:
        """Parse WooCommerce Store API response into standard ScraperResult."""
        item = None
        if isinstance(data, list):
            if not data:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=original_url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=f"Product with slug '{identifier}' not found in WooCommerce catalog.",
                    cache_policy=self._get_cache_policy()
                )
            item = data[0]
        elif isinstance(data, dict):
            item = data

        if not isinstance(item, dict):
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=original_url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Unexpected response format from WooCommerce store '{domain}'.",
                cache_policy=self._get_cache_policy()
            )

        title = item.get("name") or f"WooCommerce Product ({identifier})"

        # Extract Price & Minor Unit Conversion
        prices_obj = item.get("prices") or {}
        raw_price = prices_obj.get("price") or item.get("price")

        if raw_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=original_url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"No price information found for WooCommerce item '{identifier}'.",
                cache_policy=self._get_cache_policy()
            )

        minor_unit = prices_obj.get("currency_minor_unit", 2)
        try:
            raw_float = float(raw_price)
            # WooCommerce Store API returns minor unit integer strings (e.g. '1200' for 12.00)
            # if minor_unit > 0 and no decimal point in raw_price
            if "." not in str(raw_price) and minor_unit > 0:
                price_val = raw_float / (10 ** minor_unit)
            else:
                price_val = raw_float
        except (ValueError, TypeError):
            price_val = None

        normalized_price = self.normalize_price(price_val)
        if normalized_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=original_url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Could not parse valid numeric price from '{raw_price}'.",
                cache_policy=self._get_cache_policy()
            )

        # Currency
        currency = prices_obj.get("currency_code") or item.get("currency") or "INR"
        currency = str(currency).strip().upper()

        # Image URL
        image_url = None
        images = item.get("images") or []
        if isinstance(images, list) and images:
            first_img = images[0]
            if isinstance(first_img, dict):
                image_url = first_img.get("src")
            elif isinstance(first_img, str):
                image_url = first_img

        if image_url and not (image_url.startswith("http://") or image_url.startswith("https://")):
            image_url = None

        return ScraperResult(
            success=True,
            product_name=title,
            current_price=normalized_price,
            currency=currency,
            image_url=image_url,
            site=self.SITE_NAME,
            product_url=original_url,
            source_category=SourceCategory.PUBLIC_STORE_API,
            is_commercial_store=True,
            error=None,
            cache_policy=self._get_cache_policy(),
            attribution="Product data sourced via public WooCommerce Store API."
        )
