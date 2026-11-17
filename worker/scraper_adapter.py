import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scraper.scraper_factory import scrape_product


def get_scraper_result(product_url):
    """
    Get the complete scraper result, including cache policy.
    """

    result = scrape_product(product_url)

    if not result.success:
        raise RuntimeError(f"Scraping failed: {result.error}")

    if result.current_price is None:
        raise ValueError("Scraper did not return a current price.")

    if result.cache_policy is None:
        raise ValueError("Scraper did not provide a cache policy.")

    return result


def get_current_price(product_url, site=None):
    """
    Return only the current price when needed.
    """

    result = get_scraper_result(product_url)
    return float(result.current_price)