"""
Abstract Base Class defining the universal interface for all scraper adapters.
"""

from abc import ABC, abstractmethod
import re
from typing import Optional, Union
from scraper.models import ScraperResult


class BaseScraper(ABC):
    """
    Abstract Base Class for all product price extraction adapters.

    Guarantees every adapter exposes can_handle, validate_url,
    extract_product_id, and scrape methods.
    """

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this adapter is designed to handle the given URL or URI."""
        pass

    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """
        Validate that the URL or URI meets structural and domain requirements.
        Returns True if valid, or False if structurally defective.
        """
        pass

    @abstractmethod
    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the platform-specific unique product identifier:
        - Barcode for Open Prices
        - Product Slug / ID for LocalStore
        - ASIN for Amazon
        - FSN / Product ID for Flipkart
        Returns None if extraction fails.
        """
        pass

    @abstractmethod
    def scrape(self, url: str) -> ScraperResult:
        """
        Execute product data retrieval and return a standardized ScraperResult.

        Must never raise unhandled network or parsing exceptions;
        errors must be packaged into ScraperResult(success=False, error=...).
        """
        pass

    @staticmethod
    def normalize_price(value: Union[str, int, float, None]) -> Optional[float]:
        """
        Cleanly normalizes numeric, string, or currency values into a positive float.
        Handles comma separators, currency symbols (₹, Rs, INR), and whitespace.
        Returns None if parsing fails.
        """
        if value is None:
            return None
        if isinstance(value, (int, float)):
            price = float(value)
            return round(price, 2) if price >= 0 else None

        # Clean string: remove symbols, whitespace, comma separators
        cleaned = str(value).strip().replace(",", "")
        cleaned = re.sub(r"[^\d.]", "", cleaned)
        try:
            price = float(cleaned)
            return round(price, 2) if price >= 0 else None
        except (ValueError, TypeError):
            return None

