"""
Standardized Pydantic models for scraper outputs and cache policies.

Guarantees type-safety, explicit data-retention controls, and clean handoff to Person 3.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SourceCategory(str, Enum):
    """Classification of data sources used across the scraper module."""
    OPEN_DATA_OBSERVATION = "open_data_observation"
    CONTROLLED_DEMO_STORE = "controlled_demo_store"
    CREDENTIAL_GATED = "credential_gated"
    POLICY_RESTRICTED = "policy_restricted"


class CachePolicy(BaseModel):
    """
    Explicit data-retention policy governing how Person 3's worker may store
    prices, metadata, and history.

    NOTE: No permissive defaults are allowed. Every adapter must explicitly declare
    its retention permissions and TTL durations.
    """
    price_ttl_seconds: int = Field(
        ...,
        description="Maximum duration (seconds) that pricing data may be cached before refresh."
    )
    metadata_ttl_seconds: int = Field(
        ...,
        description="Maximum duration (seconds) that product title/description may be cached."
    )
    allow_historical_storage: bool = Field(
        ...,
        description="Explicitly declares whether storing periodic price-history is legally permitted."
    )


class ScraperResult(BaseModel):
    """
    Standard output contract returned to Person 3 (Worker/Scheduler) and callers.

    Guarantees consistent schema regardless of whether an extraction succeeded or failed.
    """
    success: bool = Field(
        ...,
        description="True if extraction succeeded; False if failed or restricted."
    )
    product_name: Optional[str] = Field(
        default=None,
        description="Clean, normalized product title or description."
    )
    current_price: Optional[float] = Field(
        default=None,
        description="Current selling price in numeric float format (e.g., 1499.0)."
    )
    currency: str = Field(
        default="INR",
        description="Three-letter ISO currency code (default: INR)."
    )
    image_url: Optional[str] = Field(
        default=None,
        description="Direct HTTP/HTTPS URL to the product image if available."
    )
    site: str = Field(
        ...,
        description="Target site identifier (e.g., 'open_prices', 'local_store', 'amazon', 'flipkart', 'croma')."
    )
    product_url: str = Field(
        ...,
        description="Original product URL or URI query passed to the scraper."
    )
    source_category: SourceCategory = Field(
        ...,
        description="Category of the data source."
    )
    is_commercial_store: bool = Field(
        ...,
        description="False for open-data/demo sources; True for commercial stores."
    )
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp (UTC) when the check was executed."
    )
    error: Optional[str] = Field(
        default=None,
        description="Descriptive error message if success is False."
    )
    cache_policy: Optional[CachePolicy] = Field(
        default=None,
        description="Data retention policy. Must be None for policy-restricted failures (e.g., Croma)."
    )
    attribution: Optional[str] = Field(
        default=None,
        description="Mandatory legal attribution string (e.g., ODbL 1.0 or Amazon Associate notice)."
    )

    @field_validator("current_price")
    @classmethod
    def validate_price_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Price must be a non-negative number.")
        return v

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            return None
        if not (clean.startswith("http://") or clean.startswith("https://")):
            raise ValueError("Image URL must start with http:// or https://")
        return clean
