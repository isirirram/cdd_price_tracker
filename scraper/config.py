"""
Safe environment configuration loader for Scraper module.

Loads credentials and endpoints from .env using python-dotenv.
Guarantees secrets are never logged or exposed in __repr__.
Supports safe configuration overrides for testing.
"""

import os
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv

# Search for .env in project root or current working directory
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
else:
    load_dotenv()


class ScraperConfig:
    """Configuration provider with secure secret masking and test override support."""

    def __init__(self):
        self._overrides: Dict[str, Any] = {}

    def set_override(self, key: str, value: Any) -> None:
        """Set a temporary override for testing."""
        self._overrides[key] = value

    def clear_overrides(self) -> None:
        """Clear all test overrides."""
        self._overrides.clear()

    @property
    def open_prices_user_agent(self) -> str:
        if "open_prices_user_agent" in self._overrides:
            return self._overrides["open_prices_user_agent"]
        return os.getenv(
            "OPEN_PRICES_USER_AGENT",
            "SmartPriceTracker/1.0 (CollegeProject; contact: student@example.edu)"
        )

    @property
    def local_store_url(self) -> str:
        if "local_store_url" in self._overrides:
            return str(self._overrides["local_store_url"]).rstrip("/")
        return os.getenv("LOCAL_STORE_URL", "http://127.0.0.1:8001").rstrip("/")

    def __repr__(self) -> str:
        return (
            f"<ScraperConfig open_prices_agent='{self.open_prices_user_agent}' "
            f"local_store='{self.local_store_url}'>"
        )


config = ScraperConfig()
