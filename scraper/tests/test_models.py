"""
Unit tests for Scraper Pydantic models (ScraperResult, CachePolicy, SourceCategory).
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from scraper.models import CachePolicy, ScraperResult, SourceCategory


def test_source_category_enum():
    """Verify all four approved source categories are strictly defined."""
    assert SourceCategory.OPEN_DATA_OBSERVATION.value == "open_data_observation"
    assert SourceCategory.CONTROLLED_DEMO_STORE.value == "controlled_demo_store"
    assert SourceCategory.CREDENTIAL_GATED.value == "credential_gated"
    assert SourceCategory.POLICY_RESTRICTED.value == "policy_restricted"


def test_cache_policy_requires_all_fields_without_defaults():
    """Verify CachePolicy strictly requires all 3 fields and has no permissive defaults."""
    with pytest.raises(ValidationError):
        # Missing allow_historical_storage
        CachePolicy(price_ttl_seconds=3600, metadata_ttl_seconds=86400)

    with pytest.raises(ValidationError):
        # Missing price_ttl_seconds
        CachePolicy(metadata_ttl_seconds=86400, allow_historical_storage=True)

    valid_policy = CachePolicy(
        price_ttl_seconds=3600,
        metadata_ttl_seconds=86400,
        allow_historical_storage=False
    )
    assert valid_policy.price_ttl_seconds == 3600
    assert valid_policy.metadata_ttl_seconds == 86400
    assert valid_policy.allow_historical_storage is False


def test_scraper_result_success():
    """Verify successful ScraperResult creation and serialization."""
    policy = CachePolicy(
        price_ttl_seconds=86400,
        metadata_ttl_seconds=86400,
        allow_historical_storage=True
    )
    result = ScraperResult(
        success=True,
        product_name="Sample Audio Headphones",
        current_price=1499.0,
        currency="INR",
        site="local_store",
        product_url="http://127.0.0.1:8000/products/product-001",
        source_category=SourceCategory.CONTROLLED_DEMO_STORE,
        is_commercial_store=False,
        cache_policy=policy
    )
    assert result.success is True
    assert result.current_price == 1499.0
    assert result.currency == "INR"
    assert result.cache_policy.allow_historical_storage is True

    # Check model dump
    dump = result.model_dump()
    assert dump["current_price"] == 1499.0
    assert dump["source_category"] == "controlled_demo_store"


def test_scraper_result_rejects_negative_price():
    """Verify that negative price raises validation error."""
    with pytest.raises(ValidationError):
        ScraperResult(
            success=True,
            product_name="Invalid Item",
            current_price=-50.0,
            site="open_prices",
            product_url="barcode:12345678",
            source_category=SourceCategory.OPEN_DATA_OBSERVATION,
            is_commercial_store=False
        )


def test_scraper_result_failure_without_cache_policy():
    """Verify that failure results (e.g., Croma) cleanly support cache_policy=None."""
    result = ScraperResult(
        success=False,
        product_name=None,
        current_price=None,
        site="croma",
        product_url="https://www.croma.com/p/123",
        source_category=SourceCategory.POLICY_RESTRICTED,
        is_commercial_store=True,
        error="Policy restricted",
        cache_policy=None
    )
    assert result.success is False
    assert result.cache_policy is None
    assert result.error == "Policy restricted"

