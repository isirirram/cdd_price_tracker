"""
OpenCart Adapter - Slot 11 (Priority 2).

Extracts live product titles, current prices, currencies, and image URLs
using OpenCart storefront structured data (Schema.org JSON-LD and OpenGraph tags).
Gracefully handles restricted or authenticated OpenCart installations.
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


class OpenCartAdapter(BaseScraper):
    """
    Adapter for OpenCart stores using public storefront structured data.

    Category: PUBLIC_STORE_API
    Commercial Store: True
    Cache Policy:
      - Price TTL: 3600 seconds (1 hour)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: True
    """

    SITE_NAME = "opencart"
    PRODUCT_ID_PATTERN = re.compile(r"[?&]product_id=(\d+)", re.IGNORECASE)

    def can_handle(self, url: str) -> bool:
        """
        Check if URL targets an OpenCart store.
        Matches opencart: URIs, domain containing 'opencart',
        or standard OpenCart query parameters (route=product/product or product_id=).
        """
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()

        if clean_url.startswith("opencart:") or clean_url.startswith("opencart://"):
            return True
        if "opencart" in clean_url:
            return True
        if "route=product/product" in clean_url or "product_id=" in clean_url:
            return True

        return False

    def validate_url(self, url: str) -> bool:
        """Verify URL structure conforms to OpenCart conventions."""
        if not self.can_handle(url):
            return False
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the OpenCart product ID or SEO slug from URL.
        Example: /index.php?route=product/product&product_id=42 -> '42'
        """
        if not url:
            return None
        clean_url = url.strip()

        # Handle opencart:// or opencart: URIs
        if clean_url.startswith("opencart://"):
            clean_url = "https://" + clean_url[len("opencart://"):]
        elif clean_url.startswith("opencart:"):
            clean_url = "https://" + clean_url[len("opencart:"):]

        try:
            parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
            match = self.PRODUCT_ID_PATTERN.search(clean_url)
            if match:
                return match.group(1)

            query_params = parse_qs(parsed.query)
            if "product_id" in query_params and query_params["product_id"]:
                return query_params["product_id"][0].strip()

            # Path fallback for OpenCart SEO URLs (e.g. /iphone)
            path_parts = [p for p in parsed.path.split("/") if p]
            if path_parts:
                slug = path_parts[-1].lower()
                if slug not in ("index.php", "cart", "checkout", "login"):
                    return slug
        except Exception:
            pass

        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Return standardized cache policy for OpenCart public endpoints."""
        return CachePolicy(
            price_ttl_seconds=3600,
            metadata_ttl_seconds=86400,
            allow_historical_storage=True
        )

    def scrape(self, url: str) -> ScraperResult:
        """Retrieve live product data from OpenCart storefront via public JSON-LD/meta."""
        clean_url = url.strip()

        http_url = clean_url
        if http_url.startswith("opencart://"):
            http_url = "https://" + http_url[len("opencart://"):]
        elif http_url.startswith("opencart:"):
            http_url = "https://" + http_url[len("opencart:"):]
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
                error="Invalid OpenCart URL: Could not extract product ID (product_id=...).",
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
                    error=f"Product '{product_id}' was not found on OpenCart store '{domain}' (HTTP 404).",
                    cache_policy=self._get_cache_policy()
                )

            if resp.status_code in (401, 403):
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=f"OpenCart store '{domain}' is private, maintenance-gated, or requires login (HTTP {resp.status_code}).",
                    cache_policy=self._get_cache_policy()
                )

            resp.raise_for_status()
            html_text = resp.text

            return self._parse_opencart_content(html_text, product_id, url, domain)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Connection timed out while querying OpenCart store '{domain}'.",
                cache_policy=self._get_cache_policy()
            )
        except requests.RequestException as e:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Network error querying OpenCart store: {str(e)}",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"OpenCart extraction error: {e}", exc_info=True)
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Failed to extract OpenCart product data: {str(e)}",
                cache_policy=self._get_cache_policy()
            )

    def _parse_opencart_content(
        self,
        html_text: str,
        product_id: str,
        original_url: str,
        domain: str
    ) -> ScraperResult:
        """Parse OpenCart public HTML/JSON-LD into standard ScraperResult."""
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
            # Common OpenCart price patterns in HTML
            price_meta = re.search(
                r'<meta[^>]*property=[\'"]product:price:amount[\'"][^>]*content=[\'"](.*?)[\'"]',
                html_text,
                re.IGNORECASE
            )
            if price_meta:
                raw_price = price_meta.group(1).strip()
            else:
                # OpenCart price element regex: e.g. <h2>$122.00</h2> or class="price"
                price_match = re.search(r'<ul[^>]*class=[\'"]list-unstyled price[\'"][^>]*>.*?<li><h2>(.*?)</h2>', html_text, re.DOTALL | re.IGNORECASE)
                if price_match:
                    raw_price = price_match.group(1).strip()

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
                error=f"No valid public price found on OpenCart page for product '{product_id}'.",
                cache_policy=self._get_cache_policy()
            )

        if not title:
            title = f"OpenCart Product ({product_id})"

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
            attribution="Product data sourced via OpenCart public storefront."
        )
