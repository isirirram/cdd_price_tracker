"""
Standalone CLI testing tool for the Smart Price Tracker Scraper module.

Allows manual verification of all five adapters without needing MongoDB,
Celery, or the FastAPI backend.
"""

import sys
from pathlib import Path

# Ensure workspace root is in sys.path when running as a direct script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scraper import scrape_product


def print_banner():
    print("=" * 65)
    print("      SMART PRICE TRACKER — STANDALONE SCRAPER TEST TOOL      ")
    print("=" * 65)


def display_result(result):
    print("\n" + "-" * 65)
    print("EXTRACTION RESULTS:")
    print("-" * 65)
    print(f"Status:             {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Target Site:        {result.site.upper()}")
    print(f"Product URL:        {result.product_url}")
    print(f"Source Category:    {result.source_category.value}")
    print(f"Commercial Store:   {'Yes' if result.is_commercial_store else 'No'}")
    print(f"Checked At (UTC):   {result.checked_at.isoformat()}")

    if result.success:
        print(f"Product Title:      {result.product_name}")
        print(f"Current Price:      {result.currency} {result.current_price:,.2f}")
        print(f"Product Image:      {result.image_url or 'None'}")
    else:
        print(f"Product Image:      {result.image_url or 'None'}")
        print(f"Error Message:      {result.error}")

    if result.cache_policy:
        print("\nDATA RETENTION POLICY:")
        print(f"  - Price Cache TTL:       {result.cache_policy.price_ttl_seconds} seconds")
        print(f"  - Metadata Cache TTL:    {result.cache_policy.metadata_ttl_seconds} seconds")
        print(f"  - Historical Storage:    {'ALLOWED' if result.cache_policy.allow_historical_storage else 'PROHIBITED BY LICENSE'}")
    else:
        print("\nDATA RETENTION POLICY:  None (No data retrieved / policy restricted)")

    if result.attribution:
        print(f"\nLEGAL ATTRIBUTION:\n  {result.attribution}")

    print("-" * 65)


def main():
    print_banner()

    if len(sys.argv) > 1:
        url = sys.argv[1].strip()
    else:
        print("Supported Inputs:")
        print("  1. Open Prices barcode:   barcode:8901030825347")
        print("  2. Open Food Facts URL:   https://in.openfoodfacts.org/product/8901030825347")
        print("  3. Local Demo Store URL:  http://127.0.0.1:8001/products/product-001")
        print("  4. Croma URL:             https://www.croma.com/sample-product/p/123456")
        print("  5. Shopify URL:           https://store.myshopify.com/products/snowboard")
        print("  6. WooCommerce URL:       https://example.com/product/flying-ninja")
        print("  7. BigCommerce URL:       https://store.mybigcommerce.com/products/sample-item")
        print("  8. Wix URL:               https://store.wixsite.com/site/product-page/summer-dress")
        print("  9. PrestaShop URL:        https://store.com/12-printed-summer-dress.html")
        print(" 10. OpenCart URL:          https://store.com/index.php?route=product/product&product_id=42")
        print(" 11. Generic E-commerce:    https://www.yeti.com/drinkware/tumblers/21071509045.html")
        print("-" * 65)
        try:
            url = input("Enter shopping product URL or barcode: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            return

    if not url:
        print("Error: Input cannot be empty.")
        return

    print(f"\nProcessing: {url} ...")
    result = scrape_product(url)
    display_result(result)


if __name__ == "__main__":
    main()
