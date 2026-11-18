"""
Unit and integration tests for GenericEcommerceAdapter (Slot 12).

Tests structured metadata extraction:
- Method 1: Schema.org JSON-LD (Product, ProductGroup, @graph, variants, offers)
- Method 2: Open Graph meta tags (og:title, og:image, product:price:amount)
- Method 3: Standard meta tags (twitter:title, twitter:image, meta price)
- Error handling, HTTP codes (404, 403), SSRF protections, edge cases.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from scraper.integrations.generic import GenericEcommerceAdapter
from scraper.models import SourceCategory
from scraper.scraper_factory import scrape_product


@pytest.fixture
def adapter():
    return GenericEcommerceAdapter()


# ==============================================================================
# 1. URL Validation & Identification
# ==============================================================================

def test_generic_can_handle_valid_urls(adapter):
    """Verify generic scraper handles arbitrary shopping websites."""
    assert adapter.can_handle("https://www.yeti.com/drinkware/tumblers/21071509045.html")
    assert adapter.can_handle("https://shop.nordstrom.com/s/item-name/12345")
    assert adapter.can_handle("http://store.example.com/item/42")


def test_generic_excludes_dedicated_and_unsupported_domains(adapter):
    """Verify generic scraper rejects domains reserved for other adapters or blocked by policy."""
    assert not adapter.can_handle("https://dummyjson.com/products/1")
    assert not adapter.can_handle("https://myntra.com/product/1234")
    assert not adapter.can_handle("https://ajio.com/product/5678")
    assert not adapter.can_handle("https://www.amazon.in/dp/B08L5W4SW6")
    assert not adapter.can_handle("https://www.flipkart.com/item/itm123")
    assert not adapter.can_handle("https://www.croma.com/p/123456")
    assert not adapter.can_handle("https://in.openfoodfacts.org/product/123456")


def test_generic_rejects_invalid_and_localhost_urls(adapter):
    """Verify generic scraper rejects empty, non-HTTP, and loopback URLs."""
    assert not adapter.can_handle("")
    assert not adapter.can_handle("ftp://store.com/item")
    assert not adapter.can_handle("not-a-url")
    assert not adapter.can_handle("http://localhost:8000/product")
    assert not adapter.can_handle("http://127.0.0.1:8000/product")


def test_generic_extract_product_id(adapter):
    """Verify product slug/identifier extraction from diverse URLs."""
    assert adapter.extract_product_id("https://www.yeti.com/drinkware/tumblers/21071509045.html") == "21071509045"
    assert adapter.extract_product_id("https://store.com/shoes/running-sneaker.htm") == "running-sneaker"
    assert adapter.extract_product_id("https://store.com/items/456") == "456"


# ==============================================================================
# 2. Method 1: Schema.org JSON-LD Extraction
# ==============================================================================

def test_generic_extracts_schema_org_json_ld(adapter):
    """Verify successful extraction from standard Schema.org Product JSON-LD."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>YETI Rambler 20 oz Tumbler | YETI</title>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org/",
            "@type": "Product",
            "name": "Rambler 20 oz Tumbler",
            "image": [
                "https://www.yeti.com/images/rambler-20-navy.jpg"
            ],
            "description": "Insulated stainless steel tumbler.",
            "brand": {
                "@type": "Brand",
                "name": "YETI"
            },
            "offers": {
                "@type": "Offer",
                "priceCurrency": "USD",
                "price": "35.00",
                "availability": "https://schema.org/InStock",
                "url": "https://www.yeti.com/drinkware/tumblers/21071509045.html"
            }
        }
        </script>
    </head>
    <body><h1>Product Page</h1></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://www.yeti.com/drinkware/tumblers/21071509045.html")

    assert res.success is True
    assert res.product_name == "Rambler 20 oz Tumbler"
    assert res.current_price == 35.00
    assert res.currency == "USD"
    assert res.image_url == "https://www.yeti.com/images/rambler-20-navy.jpg"
    assert res.site == "yeti.com"
    assert res.cache_policy.allow_historical_storage is True
    assert res.cache_policy.price_ttl_seconds == 3600


def test_generic_extracts_json_ld_nested_graph(adapter):
    """Verify extraction when Product is embedded in a complex @graph array."""
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Organization",
                    "name": "YETI Coolers",
                    "url": "https://www.yeti.com"
                },
                {
                    "@type": "WebPage",
                    "name": "Tumblers Collection"
                },
                {
                    "@type": "Product",
                    "name": "YETI Tundra 45 Hard Cooler",
                    "image": "https://yeti.com/images/tundra45.png",
                    "offers": {
                        "@type": "AggregateOffer",
                        "lowPrice": "325.00",
                        "highPrice": "350.00",
                        "priceCurrency": "USD",
                        "offerCount": "5"
                    }
                }
            ]
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://www.yeti.com/coolers/tundra-45.html")

    assert res.success is True
    assert res.product_name == "YETI Tundra 45 Hard Cooler"
    assert res.current_price == 325.00
    assert res.currency == "USD"
    assert res.image_url == "https://yeti.com/images/tundra45.png"


def test_generic_extracts_product_group_variants(adapter):
    """Verify extraction from ProductGroup with hasVariant."""
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "ProductGroup",
            "name": "Rambler French Press",
            "image": "/images/frenchpress.jpg",
            "hasVariant": [
                {
                    "@type": "Product",
                    "name": "Rambler 34 oz French Press",
                    "offers": {
                        "@type": "Offer",
                        "price": "110.00",
                        "priceCurrency": "USD",
                        "availability": "https://schema.org/InStock"
                    }
                }
            ]
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://www.yeti.com/drinkware/french-press.html")

    assert res.success is True
    assert "French Press" in res.product_name
    assert res.current_price == 110.00
    assert res.currency == "USD"
    # Relative image /images/frenchpress.jpg should be safely resolved
    assert res.image_url == "https://www.yeti.com/images/frenchpress.jpg"


def test_generic_json_ld_multiple_offers_picks_in_stock_lowest(adapter):
    """Verify adapter prioritizes in-stock offer and picks the best (lowest) price."""
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Multi-Seller Mug",
            "image": "https://store.com/mug.jpg",
            "offers": [
                {"@type": "Offer", "price": "15.00", "priceCurrency": "USD", "availability": "https://schema.org/OutOfStock"},
                {"@type": "Offer", "price": "22.50", "priceCurrency": "USD", "availability": "https://schema.org/InStock"},
                {"@type": "Offer", "price": "28.00", "priceCurrency": "USD", "availability": "https://schema.org/InStock"}
            ]
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://shop.outdoor.com/items/mug")

    assert res.success is True
    assert res.current_price == 22.50
    assert res.currency == "USD"


# ==============================================================================
# 3. Method 2 & 3: Open Graph and Structured Meta Fallback
# ==============================================================================

def test_generic_falls_back_to_open_graph(adapter):
    """Verify fallback to Open Graph metadata when JSON-LD is absent."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ignore generic page title</title>
        <meta property="og:title" content="Titanium Camp Stove" />
        <meta property="og:image" content="//cdn.outdoor.com/images/stove.png" />
        <meta property="product:price:amount" content="89.95" />
        <meta property="product:price:currency" content="EUR" />
    </head>
    <body><h1>Camp Stove</h1></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://www.campgear.com/stoves/titanium-stove")

    assert res.success is True
    assert res.product_name == "Titanium Camp Stove"
    assert res.current_price == 89.95
    assert res.currency == "EUR"
    # Protocol-relative URL //cdn.outdoor.com/images/stove.png should resolve to https:
    assert res.image_url == "https://cdn.outdoor.com/images/stove.png"


def test_generic_falls_back_to_standard_meta_and_title(adapter):
    """Verify fallback to twitter cards, standard meta price, and cleaned title."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Leather Backpack - Heritage Outfitters | Store</title>
        <meta name="twitter:title" content="Leather Backpack" />
        <meta name="twitter:image" content="https://heritage.com/bag.jpg" />
        <meta name="price" content="149.00" />
        <meta name="priceCurrency" content="GBP" />
    </head>
    <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://heritage.com/bags/leather-backpack")

    assert res.success is True
    assert res.product_name == "Leather Backpack"
    assert res.current_price == 149.00
    assert res.currency == "GBP"
    assert res.image_url == "https://heritage.com/bag.jpg"


# ==============================================================================
# 4. Error Handling and Edge Cases
# ==============================================================================

def test_generic_missing_price_returns_clean_failure(adapter):
    """Verify that pages without any structured price return success=False without crashing."""
    html = """
    <html>
    <head>
        <meta property="og:title" content="Blog Post: 10 Best Tumblers" />
        <meta property="og:image" content="https://store.com/blog.jpg" />
    </head>
    <body><p>No price anywhere.</p></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://store.com/blog/best-tumblers")

    assert res.success is False
    assert "No valid structured product price found" in res.error
    assert res.site == "store.com"


def test_generic_missing_image_succeeds_with_none(adapter):
    """Verify missing image returns None for image_url while extraction succeeds."""
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Digital Gift Card",
            "offers": {
                "@type": "Offer",
                "price": "50.00",
                "priceCurrency": "USD"
            }
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://store.com/products/gift-card")

    assert res.success is True
    assert res.product_name == "Digital Gift Card"
    assert res.current_price == 50.00
    assert res.image_url is None


def test_generic_malformed_json_ld_falls_back_gracefully(adapter):
    """Verify malformed JSON-LD syntax does not throw and allows meta fallback."""
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        { BAD JSON SYNTAX missing colon and brackets
        </script>
        <meta property="og:title" content="Fallback Cap" />
        <meta property="og:image" content="https://store.com/cap.png" />
        <meta property="product:price:amount" content="25.00" />
    </head>
    <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://store.com/gear/cap")

    assert res.success is True
    assert res.product_name == "Fallback Cap"
    assert res.current_price == 25.00
    assert res.image_url == "https://store.com/cap.png"


def test_generic_http_404_handling(adapter):
    """Verify HTTP 404 returns clean product not found failure."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://www.yeti.com/drinkware/tumblers/missing.html")

    assert res.success is False
    assert "404" in res.error
    assert "yeti.com" in res.site


def test_generic_http_403_anti_bot_handling(adapter):
    """Verify HTTP 403 returns clear anti-bot / restricted error."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = adapter.scrape("https://www.yeti.com/drinkware/tumblers/bot-blocked.html")

    assert res.success is False
    assert "anti-bot" in res.error.lower() or "403" in res.error


def test_generic_ssrf_rejection(adapter):
    """Verify SSRF attempts against private or loopback ranges are rejected immediately."""
    res = adapter.scrape("http://192.168.1.50/admin/secret-product")
    assert res.success is False
    assert "Security rejection" in res.error or "private" in res.error.lower()


def test_generic_via_public_facade():
    """Verify end-to-end integration through scrape_product facade."""
    html = """
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "YETI Colster Can Cooler",
            "image": "https://yeti.com/colster.jpg",
            "offers": {"@type": "Offer", "price": "25.00", "priceCurrency": "USD"}
        }
        </script>
    </head>
    <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()

    with patch("scraper.security.safe_get", return_value=mock_resp):
        res = scrape_product("https://www.yeti.com/drinkware/can-coolers/colster.html")

    assert res.success is True
    assert res.product_name == "YETI Colster Can Cooler"
    assert res.current_price == 25.00
    assert res.currency == "USD"
    assert res.image_url == "https://yeti.com/colster.jpg"
    assert res.source_category == SourceCategory.PUBLIC_STORE_API
