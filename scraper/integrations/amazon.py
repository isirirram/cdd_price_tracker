"""
Amazon Creators API Adapter - Slot 3 (Credential-Gated Commercial Integration).

Implements the official Amazon Creators API specification (OAuth 2.0).
Enforces the mandatory 1-hour price cache limitation and forbids permanent
historical price-history retention per Amazon Operating Agreement.
"""

import logging
import re
from typing import Optional
import requests

from scraper.base_scraper import BaseScraper
from scraper.config import config
from scraper.exceptions import ApiCredentialsMissingError
from scraper.models import CachePolicy, ScraperResult, SourceCategory

logger = logging.getLogger(__name__)


class AmazonCreatorsAdapter(BaseScraper):
    """
    Adapter for Amazon India using the official Amazon Creators API.

    Category: CREDENTIAL_GATED
    Commercial Store: True
    Cache Policy:
      - Price TTL: 3600 seconds (Strict 1-hour maximum)
      - Metadata TTL: 86400 seconds (24 hours)
      - Historical Storage: False (Permanently prohibited by Amazon's license)
    """

    SITE_NAME = "amazon"
    OAUTH_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
    CREATORS_API_ENDPOINT = "https://creatorsapi.amazon/catalog/v1/getItems"

    ASIN_PATTERNS = [
        re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE),
        re.compile(r"/gp/product/([A-Z0-9]{10})", re.IGNORECASE),
        re.compile(r"/product/([A-Z0-9]{10})", re.IGNORECASE),
        re.compile(r"^asin:([A-Z0-9]{10})$", re.IGNORECASE),
        re.compile(r"^([A-Z0-9]{10})$", re.IGNORECASE),
    ]

    def can_handle(self, url: str) -> bool:
        """Check if URL targets Amazon India or explicit ASIN."""
        if not url or not isinstance(url, str):
            return False
        clean_url = url.strip().lower()
        if "amazon.in" in clean_url or "amzn.in" in clean_url or clean_url.startswith("asin:"):
            return True
        return False

    def validate_url(self, url: str) -> bool:
        """Verify that a valid 10-character alphanumeric ASIN can be extracted."""
        return self.extract_product_id(url) is not None

    def extract_product_id(self, url: str) -> Optional[str]:
        """Extract the 10-character Amazon Standard Identification Number (ASIN)."""
        if not url:
            return None
        clean_url = url.strip()
        for pattern in self.ASIN_PATTERNS:
            match = pattern.search(clean_url)
            if match:
                return match.group(1).upper()
        return None

    def _get_cache_policy(self) -> CachePolicy:
        """
        Enforce Amazon Creators API Operating Agreement terms:
        - Price caching strictly limited to 1 hour (3600s).
        - Permanent historical price storage is prohibited.
        """
        return CachePolicy(
            price_ttl_seconds=3600,             # Exactly 1 hour
            metadata_ttl_seconds=86400,         # 24 hours
            allow_historical_storage=False      # Strictly forbidden by license
        )

    def scrape(self, url: str) -> ScraperResult:
        """
        Query Amazon Creators API if credentials are present, or return
        clear credential-gated failure status.
        """
        asin = self.extract_product_id(url)
        if not asin:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error="Invalid Amazon URL: Could not extract valid 10-character ASIN.",
                cache_policy=self._get_cache_policy()
            )

        # Check credentials
        cred_id = config.amazon_credential_id
        cred_secret = config.amazon_credential_secret
        partner_tag = config.amazon_partner_tag

        if not (cred_id and cred_secret):
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=(
                    "Amazon Creators API credentials missing. Set AMAZON_CREDENTIAL_ID and "
                    "AMAZON_CREDENTIAL_SECRET in .env. Note: Access requires an active Amazon Associates "
                    "account with at least 10 qualifying sales in the trailing 30 days."
                ),
                cache_policy=self._get_cache_policy(),
                attribution="Amazon Associates Program (Creators API)"
            )

        # Real API request logic
        try:
            # 1. Obtain OAuth 2.0 Bearer Token
            token_payload = {
                "grant_type": "client_credentials",
                "client_id": cred_id,
                "client_secret": cred_secret,
                "scope": "creatorsapi::catalog"
            }
            token_resp = requests.post(self.OAUTH_TOKEN_URL, data=token_payload, timeout=10)
            if token_resp.status_code != 200:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.CREDENTIAL_GATED,
                    is_commercial_store=True,
                    error=f"Amazon OAuth 2.0 authentication failed (HTTP {token_resp.status_code}). Verify credential eligibility.",
                    cache_policy=self._get_cache_policy()
                )
            access_token = token_resp.json().get("access_token")

            # 2. Query Creators API getItems
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "x-amz-target": "com.amazon.creatorsapi.v1.CatalogService.GetItems"
            }
            body = {
                "itemIds": [asin],
                "partnerTag": partner_tag or "tracker-21",
                "partnerType": "Associates",
                "marketplace": "www.amazon.in",
                "resources": [
                    "itemInfo.title",
                    "offersV2.listings.price"
                ]
            }
            api_resp = requests.post(self.CREATORS_API_ENDPOINT, json=body, headers=headers, timeout=10)
            if api_resp.status_code != 200:
                return ScraperResult(
                    success=False,
                    site=self.SITE_NAME,
                    product_url=url,
                    source_category=SourceCategory.CREDENTIAL_GATED,
                    is_commercial_store=True,
                    error=f"Amazon Creators API request failed (HTTP {api_resp.status_code}): {api_resp.text}",
                    cache_policy=self._get_cache_policy()
                )

            data = api_resp.json()
            return self._parse_api_response(data, asin, url)

        except requests.Timeout:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error="Timeout connecting to Amazon Creators API.",
                cache_policy=self._get_cache_policy()
            )
        except Exception as e:
            logger.error(f"Amazon Creators API exception: {e}")
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=f"Amazon Creators API error: {str(e)}",
                cache_policy=self._get_cache_policy()
            )

    def _parse_api_response(self, data: dict, asin: str, url: str) -> ScraperResult:
        """Parse official Amazon Creators API response."""
        items = data.get("itemsResult", {}).get("items", [])
        if not items:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=f"Product with ASIN '{asin}' was not found in Amazon India catalog.",
                cache_policy=self._get_cache_policy()
            )

        item = items[0]
        title = item.get("itemInfo", {}).get("title", {}).get("displayValue")
        listings = item.get("offersV2", {}).get("listings", [])

        if not listings:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=f"No active offers or price listings found for ASIN '{asin}'.",
                cache_policy=self._get_cache_policy()
            )

        price_obj = listings[0].get("price", {})
        raw_price = price_obj.get("amount") or price_obj.get("moneyValue", {}).get("amount")
        currency = price_obj.get("currency") or "INR"
        normalized_price = self.normalize_price(raw_price)

        if normalized_price is None:
            return ScraperResult(
                success=False,
                site=self.SITE_NAME,
                product_url=url,
                source_category=SourceCategory.CREDENTIAL_GATED,
                is_commercial_store=True,
                error=f"Could not extract numeric price for ASIN '{asin}'.",
                cache_policy=self._get_cache_policy()
            )

        return ScraperResult(
            success=True,
            product_name=title or f"Amazon Product ({asin})",
            current_price=normalized_price,
            currency=currency,
            site=self.SITE_NAME,
            product_url=url,
            source_category=SourceCategory.CREDENTIAL_GATED,
            is_commercial_store=True,
            error=None,
            cache_policy=self._get_cache_policy(),
            attribution="Amazon product data sourced via official Creators API. Price and availability accurate as of checked timestamp."
        )

