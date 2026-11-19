"""Product logic shared by the REST endpoints (main.py) and the chatbot (chatbot.py)."""

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from bson import ObjectId
from bson.errors import InvalidId

from models import ProductCreate

# Sites we can't track: Amazon and Flipkart only give prices through partner
# APIs we don't have access to, and Croma's terms forbid automated price
# monitoring. Scraping their pages would break their terms of service.
UNSUPPORTED_SITES = {
    "amazon.": "Amazon",
    "amzn.": "Amazon",
    "flipkart.": "Flipkart",
    "croma.": "Croma",
}

LOCAL_HOSTS = {"127.0.0.1", "localhost"}

# Store platforms that can be used for cross-store price comparison, and the
# product URL shape each one uses (the same patterns the scraper adapters use).
SHOPIFY_PATH = re.compile(r"/products/[a-zA-Z0-9_-]+(?:[/?#.]|$)")
WOOCOMMERCE_PATH = re.compile(r"/product/[a-zA-Z0-9_-]+(?:[/?#]|$)")
COMPARE_PLATFORMS = ("shopify", "woocommerce")


class UnsupportedSiteError(ValueError):
    pass


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def unsupported_site(url: str) -> str | None:
    """Name of the blocked site this URL points to, or None if it's allowed."""
    host = _host(url)
    for marker, name in UNSUPPORTED_SITES.items():
        if host.startswith(marker) or f".{marker}" in host:
            return name
    return None


def check_supported(url: str) -> None:
    site = unsupported_site(url)
    if site:
        raise UnsupportedSiteError(
            f"{site} is not supported: it doesn't allow price tracking without "
            "an official partner API. Try a Shopify or WooCommerce store, or the demo store."
        )


def detect_site(url: str) -> str:
    """First guess at the website name; the worker replaces it after scraping."""
    host = _host(url)
    if host in LOCAL_HOSTS:
        return "Demo Store"
    return host.removeprefix("www.") or "other"


def compare_platform(url: str) -> str | None:
    """'shopify' / 'woocommerce' if the URL looks like a product page on one
    of those platforms, else None. The worker confirms it when it scrapes."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host or host in LOCAL_HOSTS or unsupported_site(url):
        return None
    if "myshopify.com" in host or SHOPIFY_PATH.search(parsed.path):
        return "shopify"
    if WOOCOMMERCE_PATH.search(parsed.path) or "product" in parse_qs(parsed.query):
        return "woocommerce"
    return None


def create_product(db, payload: ProductCreate, group_id: str | None = None) -> dict:
    """Insert a new tracked product and return the stored document.

    group_id links this product to another one as "the same product on a
    different store" (used by the price comparison feature).
    """
    url = str(payload.product_url)
    check_supported(url)

    doc = {
        "user_id": payload.user_id,
        "product_name": payload.product_name or "Pending first price check",
        "product_url": url,
        "site": detect_site(url),
        "target_price": payload.target_price,
        "current_price": None,
        "alert_sent": False,
        "notify_email": str(payload.notify_email) if payload.notify_email else None,
        "telegram_chat_id": payload.telegram_chat_id,
        "image_url": None,  # filled in by the worker after the first scrape
        "created_at": datetime.now(timezone.utc),
    }
    if group_id:
        doc["group_id"] = group_id
    result = db.products.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


# ------------------------------------------------------- price comparison
def group_key(product: dict) -> str:
    """Every product in a comparison group shares the id of the first one."""
    return product.get("group_id") or str(product["_id"])


def group_products(db, product: dict) -> list[dict]:
    key = group_key(product)
    query = {"group_id": key}
    try:
        query = {"$or": [{"_id": ObjectId(key)}, {"group_id": key}]}
    except (InvalidId, TypeError):
        pass
    return list(db.products.find(query).sort("created_at", 1))


def build_comparison(products: list[dict]) -> dict:
    """Offers for the same product across stores, cheapest first."""
    offers = []
    for p in products:
        offers.append(
            {
                "id": str(p["_id"]),
                "product_name": p.get("product_name"),
                "product_url": p["product_url"],
                "site": p.get("site", "other"),
                "platform": p.get("platform") or compare_platform(p["product_url"]),
                "current_price": p.get("current_price"),
                "image_url": p.get("image_url"),
                "last_checked_at": p.get("last_checked_at"),
                "last_error": p.get("last_error"),
                "is_cheapest": False,
            }
        )

    priced = [o for o in offers if o["current_price"] is not None]
    priced.sort(key=lambda o: o["current_price"])
    unpriced = [o for o in offers if o["current_price"] is None]

    cheapest = priced[0] if priced else None
    if cheapest:
        cheapest["is_cheapest"] = True

    return {
        "offers": priced + unpriced,
        "store_count": len(offers),
        "cheapest_id": cheapest["id"] if cheapest else None,
        "cheapest_price": cheapest["current_price"] if cheapest else None,
        "cheapest_site": cheapest["site"] if cheapest else None,
        # How much you save by buying at the cheapest store vs the dearest one
        "max_saving": (
            round(priced[-1]["current_price"] - priced[0]["current_price"], 2)
            if len(priced) >= 2
            else 0.0
        ),
    }
