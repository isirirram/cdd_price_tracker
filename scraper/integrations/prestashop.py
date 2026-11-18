"""
PrestaShop Adapter - Slot 10 (Priority 2).

Extracts live product titles, current prices, currencies, and image URLs
using PrestaShop storefront structured data (Schema.org JSON-LD).
Handles stores with protected Web Service APIs (HTTP 401) and private catalogs gracefully.
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


class PrestaShopAdapter(BaseScraper):
    """
    Adapter for PrestaShop stores using public storefront structured data.

    Category: PUBLIC_STORE_API
    Commercial Store: True
    Cache Policy:
      - Price TTL: 3600 seconds (1 hour)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: True
    """

    SITE_NAME = "prestashop"
    # PrestaShop standard URL patterns: /12-product-name.html or ?id_product=12
    REWRITE_PATTERN = re.compile(r"/(\d+)-([a-zA-Z0-9_-]+)\.html", re.IGNORECASE)

    def can_handle(self, url: str) -> bool:
        """
        Check if URL targets a PrestaShop store.
        Matches prestashop: URIs, domain containing 'prestashop',
        or standard PrestaShop rewrite patterns (/12-product.html or id_product=).
        """
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()

        if clean_url.startswith("prestashop:") or clean_url.startswith("prestashop://"):
            return True
        if "prestashop" in clean_url:
            return True
        if "id_product=" in clean_url:
            return True
        if self.REWRITE_PATTERN.search(clean_url):
            return True

        return False

    def validate_url(self, url: str) -> bool:
        """Verify URL structure conforms to PrestaShop conventions."""
        if not self.can_handle(url):
            return False
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the PrestaShop product ID or slug from URL.
        Example: /12-printed-summer-dress.html -> '12'
        Example: ?id_product=12 -> '12'
        """
        if not url:
            return None
        clean_url = url.strip()

        # Handle prestashop:// or prestashop: URIs
        if clean_url.startswith("prestashop://"):
            clean_url = "https://" + clean_url[len("prestashop://"):]
        elif clean_url.startswith("prestashop:"):
            clean_url = "https://" + clean_url[len("prestashop:"):]

        try:
            parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
            match = self.REWRITE_PATTERN.search(parsed.path)
            if match:
                return match.group(1)

            query_params = parse_qs(parsed.query)
            if "id_product" in query_params and query_params["id_product"]:
                return query_params["id_product"][0].strip()
        except Exception:
            pass

        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Return standardized cache policy for PrestaShop public endpoints."""
        return CachePolicy(
            price_ttl_seconds=3600,
            metadata_ttl_seconds=86400,
            allow_historical_storage=True
        )

    def scrape(self, url: str) -> ScraperResult:
        """Retrieve live product data from PrestaShop storefront via public JSON-LD."""
        clean_url = url.strip()

        http_url = clean_url
        if http_url.startswith("prestashop://"):
            http_url = "https://" + http_url[len("prestashop://"):]
        elif http_url.startswith("prestashop:"):
            http_url = "https://" + http_url[len("prestashop:"):]
        elif not (http_url.startswith("http://") or http_url.startswith("https://")):
            http_url = f"https://{http_url}"

        # 1. SSRF Validation
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

        # 2. Extract Product ID
        product_id = self.extract_product_id(validated_url)
        if not product_id:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error="Invalid PrestaShop URL: Could not extract product ID (id_product or /{id}-{slug}.html).",
                cache_policy=self._get_cache_policy()
            )

        parsed = urlparse(validated_url)
        domain = parsed.netloc

        # 3. Query Public Storefront Page
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
                    error=f"Product '{product_id}' was not found on PrestaShop store '{domain}' (HTTP 404).",
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
                        f"PrestaShop store '{domain}' requires authentication (Web Service API key or login) "
                        f"(HTTP {resp.status_code})."
                    ),
                    cache_policy=self._get_cache_policy()
                )

            resp.raise_for_status()
            html_text = resp.text

            return self._parse_prestashop_content(html_text, product_id, url, domain)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Connection timed out while querying PrestaShop store '{domain}'.",
                cache_policy=self._get_cache_policy()
            )
        except requests.RequestException as e:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Network error querying PrestaShop store: {str(e)}",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"PrestaShop extraction error: {e}", exc_info=True)
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Failed to extract PrestaShop product data: {str(e)}",
                cache_policy=self._get_cache_policy()
            )

    def _parse_prestashop_content(
        self,
        html_text: str,
        product_id: str,
        original_url: str,
        domain: str
    ) -> ScraperResult:
        """Parse PrestaShop public HTML/JSON-LD into standard ScraperResult."""
        json_ld_nodes = security.extract_json_ld(html_text)
        product_node = security.find_product_in_json_ld(json_ld_nodes)

        title = None
        raw_price = None
        currency = "INR"
        image_url = None

        if product_node:
            title = product_node.get("name")
            offers = product_node.get("offers")
            offer_dict = None
            if isinstance(offers, dict):
                offer_dict = offers
            elif isinstance(offers, list) and offers:
                offer_dict = offers[0] if isinstance(offers[0], dict) else None

            if offer_dict:
                raw_price = offer_dict.get("price") or offer_dict.get("lowPrice")
                currency = offer_dict.get("priceCurrency") or currency

            img = product_node.get("image")
            if isinstance(img, str):
                image_url = img
            elif isinstance(img, list) and img:
                image_url = img[0] if isinstance(img[0], str) else None
            elif isinstance(img, dict):
                image_url = img.get("url")

        # Fallback to OpenGraph / Meta
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

        if not image_url:
            og_img = re.search(r'<meta[^>]*property=[\'"]og:image[\'"][^>]*content=[\'"](.*?)[\'"]', html_text, re.IGNORECASE)
            if og_img:
                image_url = og_img.group(1).strip()

        normalized_price = self.normalize_price(raw_price)
        if normalized_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=original_url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"No valid public price found on PrestaShop page for product '{product_id}'.",
                cache_policy=self._get_cache_policy()
            )

        if not title:
            title = f"PrestaShop Product ({product_id})"

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
            attribution="Product data sourced via PrestaShop public storefront."
        )
