"""
Generic E-commerce Product Scraper Adapter - Slot 12.

Extracts live product titles, current prices, currencies, and image URLs
from any publicly accessible shopping website using structured metadata:
1. Method 1: Schema.org JSON-LD (<script type="application/ld+json">, Product, ProductGroup, offers)
2. Method 2: Open Graph product metadata (og:title, og:image, product:price:amount)
3. Method 3: Other structured metadata (twitter:title, twitter:image, meta pricing)

Enforces strict SSRF protection, private IP blocking, safe URL resolution,
and price/currency validation without fabricating data.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from scraper import security
from scraper.base_scraper import BaseScraper
from scraper.exceptions import InvalidUrlError
from scraper.models import CachePolicy, ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class GenericEcommerceAdapter(BaseScraper):
    """
    Adapter for arbitrary shopping websites using structured metadata extraction.

    Category: PUBLIC_STORE_API
    Commercial Store: True
    Cache Policy:
      - Price TTL: 3600 seconds (1 hour)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: True
    """

    SITE_NAME = "generic"

    # Domains explicitly excluded or handled by dedicated policy/adapter slots
    EXCLUDED_DOMAINS = {
        "dummyjson.com",
        "myntra.com",
        "ajio.com",
        # Amazon / Flipkart: price data only through partner APIs we don't have
        "amazon.",
        "amzn.",
        "flipkart.",
        "croma.com",
        "openfoodfacts.org",
    }

    def can_handle(self, url: str) -> bool:
        """
        Check if URL can be handled by the generic e-commerce scraper.
        Matches any valid HTTP/HTTPS URL whose domain is not explicitly excluded.
        """
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip()

        # Only accept HTTP/HTTPS
        try:
            if "://" not in clean_url:
                parsed = urlparse(f"https://{clean_url}")
            else:
                parsed = urlparse(clean_url)
            if parsed.scheme.lower() not in ("http", "https"):
                return False

            hostname = parsed.hostname.lower() if parsed.hostname else ""
            if not hostname or "." not in hostname:
                return False

            # Check if domain is in excluded set
            for ex in self.EXCLUDED_DOMAINS:
                if ex in hostname:
                    return False

            # Exclude loopback or standard private IP literals
            if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or hostname.startswith("127."):
                return False

            return True
        except Exception:
            return False

    def validate_url(self, url: str) -> bool:
        """Verify URL is structurally valid for web fetching."""
        return self.can_handle(url)

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract a plausible product slug or identifier from the URL path.
        Example: /drinkware/tumblers/21071509045.html -> '21071509045'
        """
        if not url:
            return None
        try:
            parsed = urlparse(url.strip())
            path = parsed.path.rstrip("/")
            if not path:
                return parsed.netloc or "item"

            # Remove .html, .htm, .php extensions
            path = re.sub(r"\.(?:html?|php|aspx?)$", "", path, flags=re.IGNORECASE)
            parts = [p for p in path.split("/") if p]
            if parts:
                slug = parts[-1].strip()
                if slug:
                    return slug
            return parsed.netloc
        except Exception:
            return None

    def _get_cache_policy(self) -> CachePolicy:
        """Return standardized cache policy for public e-commerce storefronts."""
        return CachePolicy(
            price_ttl_seconds=3600,         # 1-hour price cache
            metadata_ttl_seconds=86400,     # 24-hour metadata
            allow_historical_storage=True   # Permitted for public web storefront data
        )

    def scrape(self, url: str) -> ScraperResult:
        """
        Retrieve live product data from any e-commerce page via structured metadata.
        Follows priority order: Schema.org JSON-LD -> Open Graph -> Standard Meta.
        """
        clean_url = url.strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
            clean_url = f"https://{clean_url}"

        # 1. SSRF and Domain Security Validation
        try:
            validated_url = security.validate_safe_url(clean_url)
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

        parsed = urlparse(validated_url)
        domain = parsed.netloc.lower()
        site_name = domain.replace("www.", "")

        # 2. Query Public Storefront Page
        try:
            resp = security.safe_get(
                validated_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=10
            )

            if resp.status_code == 404:
                return ScraperResult(
                    success=False,
                    site=site_name,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=f"Product page not found on '{domain}' (HTTP 404).",
                    cache_policy=self._get_cache_policy()
                )

            if resp.status_code in (401, 403):
                return ScraperResult(
                    success=False,
                    site=site_name,
                    product_url=url,
                    source_category=SourceCategory.PUBLIC_STORE_API,
                    is_commercial_store=True,
                    error=(
                        f"Access to '{domain}' is restricted, password-protected, or blocked "
                        f"by anti-bot protections (HTTP {resp.status_code})."
                    ),
                    cache_policy=self._get_cache_policy()
                )

            resp.raise_for_status()
            html_text = resp.text

            return self._extract_metadata(html_text, validated_url, url, site_name)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=site_name,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Connection timed out while querying '{domain}'.",
                cache_policy=self._get_cache_policy()
            )
        except requests.RequestException as e:
            return ScraperResult(
                success=False,
                site=site_name,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"Network error querying website: {str(e)}",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"Generic scraper extraction error: {e}", exc_info=True)
            return ScraperResult(
                success=False,
                site=site_name,
                product_url=url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=security.describe_error(e, "Failed to extract product data"),
                cache_policy=self._get_cache_policy()
            )

    def _extract_metadata(
        self,
        html_text: str,
        validated_url: str,
        original_url: str,
        site_name: str
    ) -> ScraperResult:
        """
        Execute multi-method extraction:
        1. Schema.org JSON-LD
        2. Open Graph tags
        3. Standard product meta tags
        """
        product_name: Optional[str] = None
        current_price: Optional[float] = None
        currency: str = "INR"
        image_url: Optional[str] = None

        # ----------------------------------------------------------------------
        # METHOD 1: Schema.org JSON-LD (<script type="application/ld+json">)
        # ----------------------------------------------------------------------
        json_ld_nodes = security.extract_json_ld(html_text)
        product_node = security.find_product_in_json_ld(json_ld_nodes)

        if product_node:
            product_name = product_node.get("name")

            # Extract price and currency from offers or hasVariant
            offers = product_node.get("offers")
            if not offers and "hasVariant" in product_node:
                variants = product_node.get("hasVariant")
                if isinstance(variants, list):
                    variant_offers = []
                    for v in variants:
                        if isinstance(v, dict):
                            vo = v.get("offers")
                            if isinstance(vo, list):
                                variant_offers.extend(vo)
                            elif isinstance(vo, dict):
                                variant_offers.append(vo)
                    offers = variant_offers
                elif isinstance(variants, dict):
                    offers = variants.get("offers")

            price_val, curr_val = self._extract_price_from_offers(offers)
            if price_val is not None:
                current_price = price_val
            if curr_val:
                currency = curr_val

            # Extract image
            img_val = self._extract_image_from_json_ld(product_node.get("image"))
            if not img_val and "hasVariant" in product_node:
                variants = product_node.get("hasVariant")
                if isinstance(variants, list) and variants and isinstance(variants[0], dict):
                    img_val = self._extract_image_from_json_ld(variants[0].get("image"))
            if img_val:
                image_url = security.resolve_image_url(validated_url, img_val)

        # ----------------------------------------------------------------------
        # METHOD 2 & 3: Open Graph and Structured Meta Tags
        # ----------------------------------------------------------------------
        meta_tags = security.extract_meta_tags(html_text)

        # Name fallback: og:title -> twitter:title -> <title>
        if not product_name:
            product_name = meta_tags.get("og:title") or meta_tags.get("twitter:title")
            # If meta title is too generic (e.g. just site name or "Home"), clean it
            if product_name and product_name.lower() in (site_name.lower(), "home", "index"):
                product_name = None

        if not product_name:
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
            if title_match:
                raw_title = title_match.group(1).strip()
                # Remove common trailing suffixes like " | Store Name" or " - Brand"
                clean_title = re.split(r"\s+[|\-–—]\s+", raw_title)[0].strip()
                if clean_title and clean_title.lower() != site_name.lower():
                    product_name = clean_title

        # Price fallback: product:price:amount -> og:price:amount -> other meta
        if current_price is None:
            raw_meta_price = (
                meta_tags.get("product:price:amount")
                or meta_tags.get("og:price:amount")
                or meta_tags.get("price")
            )
            if raw_meta_price:
                norm = self.normalize_price(raw_meta_price)
                if norm is not None and norm > 0:
                    current_price = norm

        # Currency fallback
        if not currency or currency == "INR":
            meta_curr = (
                meta_tags.get("product:price:currency")
                or meta_tags.get("og:price:currency")
                or meta_tags.get("pricecurrency")
            )
            if meta_curr:
                currency = meta_curr.strip().upper()

        # Image fallback: og:image -> twitter:image
        if not image_url:
            raw_img = (
                meta_tags.get("og:image")
                or meta_tags.get("og:image:url")
                or meta_tags.get("og:image:secure_url")
                or meta_tags.get("twitter:image")
            )
            if raw_img:
                image_url = security.resolve_image_url(validated_url, raw_img)

        # ----------------------------------------------------------------------
        # VALIDATION & SAFETY CHECKS
        # ----------------------------------------------------------------------
        if current_price is None or current_price <= 0:
            return ScraperResult(
                success=False,
                site=site_name,
                product_url=original_url,
                source_category=SourceCategory.PUBLIC_STORE_API,
                is_commercial_store=True,
                error=f"No valid structured product price found on page '{site_name}'.",
                cache_policy=self._get_cache_policy()
            )

        if not product_name:
            slug = self.extract_product_id(validated_url)
            product_name = f"Product ({slug})" if slug else f"Product on {site_name}"

        # Ensure currency is a clean 3-letter uppercase code
        if not currency or len(currency) < 3:
            currency = "INR"

        return ScraperResult(
            success=True,
            product_name=product_name,
            current_price=current_price,
            currency=currency,
            image_url=image_url,
            site=site_name,
            product_url=original_url,
            source_category=SourceCategory.PUBLIC_STORE_API,
            is_commercial_store=True,
            error=None,
            cache_policy=self._get_cache_policy(),
            attribution="Product data sourced via public storefront structured metadata."
        )

    def _extract_price_from_offers(self, offers: Any) -> Tuple[Optional[float], Optional[str]]:
        """
        Extract the best active product price and currency from Schema.org offers.
        Handles single offers, lists, AggregateOffer, and nested offers.
        """
        if not offers:
            return None, None

        offer_list: List[Dict[str, Any]] = []
        if isinstance(offers, dict):
            # Check if it's an AggregateOffer with nested offers
            if "offers" in offers:
                nested = offers["offers"]
                if isinstance(nested, list):
                    offer_list.extend([o for o in nested if isinstance(o, dict)])
                elif isinstance(nested, dict):
                    offer_list.append(nested)

            # Check top-level AggregateOffer or single Offer
            offer_list.append(offers)
        elif isinstance(offers, list):
            offer_list.extend([o for o in offers if isinstance(o, dict)])

        valid_prices: List[Tuple[float, str, bool]] = []  # (price, currency, is_in_stock)

        for offer in offer_list:
            raw_p = offer.get("price") or offer.get("lowPrice")
            if raw_p is None:
                continue

            norm_p = self.normalize_price(raw_p)
            if norm_p is None or norm_p <= 0:
                continue

            curr = offer.get("priceCurrency") or "INR"
            curr = str(curr).strip().upper()

            # Check availability
            avail = str(offer.get("availability") or "").lower()
            in_stock = ("instock" in avail or not avail)

            valid_prices.append((norm_p, curr, in_stock))

        if not valid_prices:
            return None, None

        # Prefer in-stock offer; if multiple, pick lowest price
        in_stock_offers = [item for item in valid_prices if item[2]]
        pool = in_stock_offers if in_stock_offers else valid_prices
        pool.sort(key=lambda x: x[0])

        best = pool[0]
        return best[0], best[1]

    def _extract_image_from_json_ld(self, image_data: Any) -> Optional[str]:
        """Extract image URL from Schema.org Image, ImageObject, or string list."""
        if not image_data:
            return None
        if isinstance(image_data, str):
            return image_data.strip()
        if isinstance(image_data, list) and image_data:
            first = image_data[0]
            if isinstance(first, str):
                return first.strip()
            if isinstance(first, dict):
                return first.get("url") or first.get("contentUrl")
        if isinstance(image_data, dict):
            return image_data.get("url") or image_data.get("contentUrl")
        return None
