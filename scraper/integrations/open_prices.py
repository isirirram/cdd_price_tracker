"""
Open Prices (Open Food Facts) Adapter - Slot 1 (Open-Data Price Observation Source).

Queries the open crowd-sourced Open Prices REST API (ODbL 1.0).
Extracts product barcodes, real price observations in INR, and product image URLs.
"""

import logging
import re
from typing import Optional
import requests

from scraper.base_scraper import BaseScraper
from scraper.config import config
from scraper.models import CachePolicy, ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class OpenPricesAdapter(BaseScraper):
    """
    Adapter for retrieving price observations from Open Food Facts / Open Prices.

    Category: OPEN_DATA_OBSERVATION
    License: Open Database License (ODbL 1.0)
    Commercial Store: False
    """

    SITE_NAME = "open_prices"
    BASE_API_URL = "https://prices.openfoodfacts.org/api/v1/prices"
    PRODUCT_API_URL = "https://world.openfoodfacts.org/api/v2/product"

    BARCODE_REGEXES = [
        re.compile(r"/product/([0-9]{8,14})", re.IGNORECASE),
        re.compile(r"[?&]product_code=([0-9]{8,14})", re.IGNORECASE),
        re.compile(r"^(?:barcode:|openprices://)?([0-9]{8,14})$", re.IGNORECASE),
    ]

    def can_handle(self, url: str) -> bool:
        """Check if URL points to Open Food Facts, Open Prices, or direct barcode."""
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()
        if (
            "openfoodfacts.org" in clean_url
            or "prices.openfoodfacts" in clean_url
            or clean_url.startswith("barcode:")
            or clean_url.startswith("openprices://")
        ):
            return True
        # Bare barcode check (8 to 14 digits)
        return bool(re.match(r"^\d{8,14}$", clean_url))

    def validate_url(self, url: str) -> bool:
        """Verify that a valid 8-14 digit numeric barcode can be extracted."""
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract the numeric product barcode from the input string."""
        if not url:
            return None
        clean_url = url.strip()
        for pattern in self.BARCODE_REGEXES:
            match = pattern.search(clean_url)
            if match:
                return match.group(1)
        return None

    def _get_cache_policy(self) -> CachePolicy:
        """Explicitly defines cache retention under ODbL 1.0."""
        return CachePolicy(
            price_ttl_seconds=86400,        # 24-hour application refresh policy
            metadata_ttl_seconds=604800,    # 7-day metadata refresh
            allow_historical_storage=True   # Permitted under ODbL 1.0 terms
        )

    def scrape(self, url: str) -> ScraperResult:
        """Query Open Prices API and return standardized ScraperResult with image URL."""
        barcode = self.extract_product_id(url)
        if not barcode:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.OPEN_DATA_OBSERVATION,
                is_commercial_store=False,
                error=(
                    "Invalid Open Prices URL: A valid 8 to 14 digit numeric barcode could not be extracted. "
                    "Expected format: https://in.openfoodfacts.org/product/<barcode> or barcode:<digits>"
                ),
                cache_policy=None,
                image_url=None
            )

        headers = {"User-Agent": config.open_prices_user_agent}

        # Step 1: Query Open Prices API for prices matching the barcode
        try:
            params = {"product_code": barcode, "size": 10}
            resp = requests.get(
                self.BASE_API_URL,
                params=params,
                headers=headers,
                timeout=10
            )
            if resp.status_code == 404:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.OPEN_DATA_OBSERVATION,
                    is_commercial_store=False,
                    error=f"No price observations found for barcode '{barcode}' in Open Prices.",
                    cache_policy=self._get_cache_policy(),
                    image_url=None
                )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.OPEN_DATA_OBSERVATION,
                is_commercial_store=False,
                error="Network timeout while connecting to Open Prices API.",
                cache_policy=None,
                image_url=None
            )
        except requests.RequestException as e:
            logger.error(f"Open Prices request failed: {e}")
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.OPEN_DATA_OBSERVATION,
                is_commercial_store=False,
                error=f"Open Prices API request error: {str(e)}",
                cache_policy=None,
                image_url=None
            )

        items = data.get("items", [])
        if not items:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.OPEN_DATA_OBSERVATION,
                is_commercial_store=False,
                error=f"Product barcode {barcode} recognized, but zero price observations recorded in Open Prices.",
                cache_policy=self._get_cache_policy(),
                attribution="Price data sourced from Open Food Facts / Open Prices under ODbL 1.0",
                image_url=None
            )

        # Select price observation: prefer INR, else most recent
        selected_item = None
        for item in items:
            if item.get("currency") == "INR":
                selected_item = item
                break
        if not selected_item:
            selected_item = items[0]

        raw_price = selected_item.get("price")
        currency = selected_item.get("currency", "INR")
        normalized_price = self.normalize_price(raw_price)

        if normalized_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.OPEN_DATA_OBSERVATION,
                is_commercial_store=False,
                error=f"Invalid or missing price value in Open Prices observation for barcode {barcode}.",
                cache_policy=self._get_cache_policy(),
                attribution="Price data sourced from Open Food Facts / Open Prices under ODbL 1.0",
                image_url=None
            )

        # Step 2: Retrieve product title and image URL from Open Food Facts catalog if available
        product_name = selected_item.get("product_name")
        image_url = selected_item.get("image_url")

        if not product_name or not image_url:
            try:
                prod_resp = requests.get(
                    f"{self.PRODUCT_API_URL}/{barcode}.json",
                    params={"fields": "product_name,brands,image_url,image_front_url"},
                    headers=headers,
                    timeout=5
                )
                if prod_resp.status_code == 200:
                    prod_data = prod_resp.json().get("product", {})
                    name = prod_data.get("product_name")
                    brand = prod_data.get("brands")
                    if not product_name:
                        if name and brand:
                            product_name = f"{brand} - {name}"
                        elif name:
                            product_name = name
                    if not image_url:
                        image_url = prod_data.get("image_url") or prod_data.get("image_front_url")
            except Exception:
                pass

        if not product_name:
            product_name = f"Open Food Facts Product ({barcode})"

        return ScraperResult(
            success=True,
            product_name=product_name,
            current_price=normalized_price,
            currency=currency,
            image_url=image_url if (image_url and (image_url.startswith("http://") or image_url.startswith("https://"))) else None,
            site=self.SITE_NAME,
            product_url=url,
            source_category=SourceCategory.OPEN_DATA_OBSERVATION,
            is_commercial_store=False,
            error=None,
            cache_policy=self._get_cache_policy(),
            attribution="Price data sourced from Open Food Facts / Open Prices under ODbL 1.0"
        )
