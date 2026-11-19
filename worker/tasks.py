from datetime import datetime, timezone
from urllib.parse import urlparse

from bson import ObjectId
from bson.errors import InvalidId

from celery_app import celery_app
from database import price_history_collection, products_collection
from pymongo import ReturnDocument

from notifications import send_price_alerts
from scraper_adapter import get_scraper_result

PLACEHOLDER_NAME = "Pending first price check"

# These scraper "site" values are the platform the store runs on, not the
# store itself (e.g. "shopify"), so for them we show the store's domain.
PLATFORM_SITES = {
    "generic", "shopify", "woocommerce", "bigcommerce",
    "wix", "prestashop", "opencart",
}

FRIENDLY_SITE_NAMES = {
    "local_store": "Demo Store",
    "open_prices": "Open Prices",
}


def _now():
    return datetime.now(timezone.utc)


def _website_name(scraped_site, product_url):
    """Turn the scraper's site value into a name the UI can show."""
    site = (scraped_site or "").strip().lower()
    if site in FRIENDLY_SITE_NAMES:
        return FRIENDLY_SITE_NAMES[site]
    if site and site not in PLATFORM_SITES:
        return site  # e.g. croma, or a domain from the generic scraper
    host = (urlparse(product_url).hostname or "").lower()
    return host.removeprefix("www.") or "other"


def _record_error(oid, message):
    # Saved on the product so the frontend can show WHY there is no price yet
    # (e.g. "robots.txt disallows this page") instead of "Pending" forever.
    products_collection.update_one(
        {"_id": oid},
        {"$set": {"last_error": message, "last_checked_at": _now()}},
    )


@celery_app.task(name="tasks.check_price")
def check_price(product_id, simulated_price=None):
    try:
        oid = ObjectId(product_id)
    except (InvalidId, TypeError):
        return "Invalid product id"

    product = products_collection.find_one({"_id": oid})
    if not product:
        return "Product not found"

    product_name = product.get("product_name") or PLACEHOLDER_NAME
    product_url = product["product_url"]
    target_price = float(product["target_price"])

    # Everything we learn from this check goes into ONE $set at the end
    updates = {}

    # 1. Get the current price and the scraped metadata
    if simulated_price is not None:
        current_price = float(simulated_price)
        allow_history = False
        checked_at = _now()
    else:
        try:
            result = get_scraper_result(product_url)
        except (RuntimeError, ValueError) as exc:
            _record_error(oid, str(exc))
            return f"Price check failed: {exc}"

        current_price = float(result.current_price)
        checked_at = result.checked_at

        policy = result.cache_policy
        if policy.price_ttl_seconds <= 0 or policy.metadata_ttl_seconds <= 0:
            _record_error(oid, "Scraper returned an invalid cache policy")
            return "Invalid cache policy"
        allow_history = policy.allow_historical_storage

        # Scraped metadata. Only overwrite with real values, never with empty
        # ones, so a later scrape that misses the image doesn't wipe it.
        scraped_name = (result.product_name or "").strip()
        if scraped_name:
            product_name = scraped_name
            updates["product_name"] = scraped_name

        image_url = getattr(result, "image_url", None)
        if image_url:
            updates["image_url"] = image_url

        updates["site"] = _website_name(result.site, product_url)
        # Raw platform (shopify, woocommerce, local_store, ...) for price comparison
        updates["platform"] = (result.site or "").strip().lower() or None

    if current_price <= 0:
        _record_error(oid, "Scraper returned a non-positive price")
        return "Invalid product price"

    # 2. Save history only when the source's licence allows it
    if allow_history:
        price_history_collection.insert_one(
            {"product_id": oid, "price": current_price, "checked_at": checked_at}
        )

    # 3. Update the existing product document in one write
    updates.update(
        {
            "current_price": current_price,
            "last_checked_at": checked_at,
            "last_error": None,
        }
    )
    products_collection.update_one({"_id": oid}, {"$set": updates})

    # 4. Alert logic: send once when price first reaches the target,
    #    re-arm when it goes back above the target.
    if current_price > target_price:
        products_collection.update_one(
            {"_id": oid, "alert_sent": True}, {"$set": {"alert_sent": False}}
        )
        return "Price checked successfully!"

    # Claim the alert atomically BEFORE sending. If two checks of the same
    # product run at the same time (Beat + "Check Now", or two workers),
    # only one of them gets the document back here, so only one alert goes out.
    claimed = products_collection.find_one_and_update(
        {"_id": oid, "alert_sent": {"$ne": True}},
        {"$set": {"alert_sent": True, "alert_sent_at": _now()}},
        return_document=ReturnDocument.AFTER,
    )
    if claimed is None:
        return "Alert already sent"

    sent, problems = send_price_alerts(
        claimed,
        product_name=product_name,
        product_url=product_url,
        current_price=current_price,
        target_price=target_price,
    )

    if not sent:
        # Nothing was delivered: give the claim back so the next check retries.
        products_collection.update_one(
            {"_id": oid}, {"$set": {"alert_sent": False, "alert_sent_at": None}}
        )
        reason = "; ".join(problems) or "no alert channel is set up"
        print(f"WARNING: alert for product {product_id} not sent: {reason}")
        return f"Target reached, but alert not sent: {reason}"

    if problems:
        print(f"WARNING: some alert channels failed for {product_id}: {'; '.join(problems)}")
    return f"Price drop alert sent via {', '.join(sent)}"


@celery_app.task(name="tasks.enqueue_all_products")
def enqueue_all_products():
    count = 0
    for product in products_collection.find({}, {"_id": 1}):
        check_price.delay(str(product["_id"]))
        count += 1
    return f"Scheduled {count} products"
