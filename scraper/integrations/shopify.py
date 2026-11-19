"""
Shopify Storefront Adapter - Slot 6.

Extracts live product titles, current prices, currencies, and image URLs
using Shopify's publicly accessible Storefront Ajax endpoint (/products/{handle}.js).
Converts prices from minor currency units (cents/paise) to standard float units.
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


class ShopifyAdapter(BaseScraper):
    """
    Adapter for Shopify stores using the public Ajax Product JSON endpoint.

    Category: PUBLIC_STORE_API
    Commercial Store: True
    Cache Policy:
      - Price TTL: 3600 seconds (1 hour)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: True
    """

    SITE_NAME = "shopify"
    HANDLE_PATTERN = re.compile(
        r"/products/([a-zA-Z0-9_-]+)(?:\.js|\.json)?(?:[/?#]|$)",
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
        Check if URL targets a Shopify store.
        Matches *.myshopify.com, shopify: URIs, or standard /products/ paths.
        """
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()

        if clean_url.startswith("shopify:") or clean_url.startswith("shopify://"):
            return True

        # Do not match URLs explicitly designated for other platform schemes
        if any(clean_url.startswith(p) for p in ("bigcommerce:", "woocommerce:", "wix:", "prestashop:", "opencart:")):
            return False

        try:
            parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
            domain = parsed.netloc or ""
            if any(ex in domain for ex in self.EXCLUDED_DOMAINS):
                return False
            if "myshopify.com" in domain or "shopify.com" in domain:
                return True
            if "/products/" in parsed.path:
                return True
        except Exception:
            pass

        return False

    def validate_url(self, url: str) -> bool:
        """Verify URL structure conforms to Shopify product conventions."""
        if not self.can_handle(url):
            return False
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the Shopify product handle from the URL path.
        Example: /products/classic-leather-jacket -> 'classic-leather-jacket'
        """
        if not url:
            return None
        clean_url = url.strip()

        # Handle shopify:// or shopify: URIs
        if clean_url.startswith("shopify://"):
            clean_url = "https://" + clean_url[len("shopify://"):]
        elif clean_url.startswith("shopify:"):
            clean_url = "https://" + clean_url[len("shopify:"):]

        try:
            parsed = urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
            match = self.HANDLE_PATTERN.search(parsed.path)
            if match:
                return match.group(1).lower()
        except Exception:
            pass

        return None

    def _extract_variant_id(self, url: str) -> Optional[int]:
        """Extract optional ?variant=12345 parameter if specified."""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if "variant" in params and params["variant"]:
                return int(params["variant"][0])
        except Exception:
            pass
        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Return standardized cache policy for public storefront endpoints."""
        return CachePolicy(
            price_ttl_seconds=3600,         # 1-hour price cache
            metadata_ttl_seconds=86400,     # 24-hour metadata
            allow_historical_storage=True   # Permitted for public storefront data
        )

    def scrape(self, url: str) -> ScraperResult:
        """
        Retrieve live product data from Shopify store via /products/{handle}.js.
        """
        clean_url = url.strip()

        # Normalize shopify: schemes for HTTP resolution
        http_url = clean_url
        if http_url.startswith("shopify://"):
            http_url = "https://" + http_url[len("shopify://"):]
        elif http_url.startswith("shopify:"):
            http_url = "https://" + http_url[len("shopify:"):]
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

        # 2. Extract Product Handle
        handle = self.extract_product_id(validated_url)
        if not handle:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error="Invalid Shopify URL: Could not extract product handle (/products/{handle}).",
                cache_policy=self._get_cache_policy()
            )

        parsed = urlparse(validated_url)
        domain = parsed.netloc
        scheme = parsed.scheme or "https"
        endpoint = f"{scheme}://{domain}/products/{handle}.js"

        # 3. Query Shopify Public Ajax Endpoint
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
                    error=f"Product with handle '{handle}' was not found on Shopify store '{domain}' (HTTP 404).",
                    cache_policy=self._get_cache_policy()
                )

            if resp.status_code in (401, 403):
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=f"Access to Shopify store '{domain}' is restricted or password-protected (HTTP {resp.status_code}).",
                    cache_policy=self._get_cache_policy()
                )

            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=f"Unexpected JSON format returned by Shopify store '{domain}'.",
                    cache_policy=self._get_cache_policy()
                )

            return self._parse_shopify_json(data, handle, url, validated_url, domain)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Connection timed out while querying Shopify store '{domain}'.",
                cache_policy=self._get_cache_policy()
            )
        except requests.RequestException as e:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Network error querying Shopify endpoint: {str(e)}",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"Shopify extraction error: {e}", exc_info=True)
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=security.describe_error(e, "Failed to extract Shopify product data"),
                cache_policy=self._get_cache_policy()
            )

    def _parse_shopify_json(
        self,
        data: dict,
        handle: str,
        original_url: str,
        validated_url: str,
        domain: str
    ) -> ScraperResult:
        """Parse Shopify product JSON payload into standard ScraperResult."""
        title = data.get("title") or f"Shopify Product ({handle})"

        # Check for specific variant selection
        variant_id = self._extract_variant_id(validated_url)
        variants = data.get("variants") or []
        selected_variant = None

        if variant_id and isinstance(variants, list):
            for var in variants:
                if isinstance(var, dict) and var.get("id") == variant_id:
                    selected_variant = var
                    break

        if not selected_variant and variants and isinstance(variants[0], dict):
            selected_variant = variants[0]

        # Extract Price (Shopify Ajax API returns prices in minor currency units / cents)
        raw_price = None
        if selected_variant:
            raw_price = selected_variant.get("price")
        if raw_price is None:
            raw_price = data.get("price")

        if raw_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=original_url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"No price information found for product '{handle}'.",
                cache_policy=self._get_cache_policy()
            )

        # Convert minor units (e.g. 1999 -> 19.99, or 149900 -> 1499.0)
        try:
            if isinstance(raw_price, (int, float)):
                # If price is integer in minor units (cents)
                price_val = float(raw_price) / 100.0
            else:
                price_str = str(raw_price).strip()
                if "." in price_str:
                    # Already in decimal format
                    price_val = float(price_str)
                else:
                    price_val = float(price_str) / 100.0
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
                error=f"Could not parse numeric price from '{raw_price}'.",
                cache_policy=self._get_cache_policy()
            )

        # Extract Currency
        currency = data.get("currency")
        if not currency and selected_variant and isinstance(selected_variant, dict):
            currency = selected_variant.get("currency")
        if not currency or not isinstance(currency, str):
            currency = "INR"  # Standard project default
        currency = currency.strip().upper()

        # Extract Product Image URL
        image_url = None
        # 1. Variant image
        if selected_variant and isinstance(selected_variant.get("featured_image"), dict):
            image_url = selected_variant["featured_image"].get("src")
        # 2. Main featured_image
        if not image_url:
            image_url = data.get("featured_image")
        # 3. Images list
        if not image_url:
            images = data.get("images")
            if isinstance(images, list) and images:
                first_img = images[0]
                if isinstance(first_img, str):
                    image_url = first_img
                elif isinstance(first_img, dict):
                    image_url = first_img.get("src")

        # Normalize protocol-relative URLs (e.g., //cdn.shopify.com/... -> https://cdn.shopify.com/...)
        if image_url and isinstance(image_url, str):
            image_url = image_url.strip()
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            if not (image_url.startswith("http://") or image_url.startswith("https://")):
                image_url = None
        else:
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
            attribution="Product data sourced via public Shopify Storefront JSON endpoint."
        )
