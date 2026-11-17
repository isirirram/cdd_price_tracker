from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from celery_app import celery_app
from database import price_history_collection, products_collection
from notifications import EmailNotConfigured, send_email_alert
from scraper_adapter import get_scraper_result


def _now():
    return datetime.now(timezone.utc)


def _record_error(oid, message):
    # Saved on the product so the frontend can show WHY there is no price yet
    # (e.g. "Amazon API credentials missing") instead of "Pending" forever.
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

    product_name = product["product_name"]
    product_url = product["product_url"]
    target_price = float(product["target_price"])

    # 1. Get the current price (and whether we may store it as history)
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

        # Replace the "Pending first price check" placeholder with the real name
        if result.product_name and result.product_name != product_name:
            product_name = result.product_name
            products_collection.update_one(
                {"_id": oid}, {"$set": {"product_name": product_name}}
            )

        policy = result.cache_policy
        if policy.price_ttl_seconds <= 0 or policy.metadata_ttl_seconds <= 0:
            _record_error(oid, "Scraper returned an invalid cache policy")
            return "Invalid cache policy"

        allow_history = policy.allow_historical_storage

    if current_price <= 0:
        _record_error(oid, "Scraper returned a non-positive price")
        return "Invalid product price"

    # 2. Save history only when the source's licence allows it
    if allow_history:
        price_history_collection.insert_one(
            {"product_id": oid, "price": current_price, "checked_at": checked_at}
        )

    # 3. Update current price and clear any previous error
    products_collection.update_one(
        {"_id": oid},
        {
            "$set": {
                "current_price": current_price,
                "last_checked_at": checked_at,
                "last_error": None,
            }
        },
    )

    # 4. Alert logic: send once when price first reaches the target,
    #    re-arm when it goes back above the target.
    if current_price > target_price:
        if product.get("alert_sent"):
            products_collection.update_one({"_id": oid}, {"$set": {"alert_sent": False}})
        return "Price checked successfully!"

    if product.get("alert_sent"):
        return "Alert already sent"

    try:
        sent_to = send_email_alert(
            product_name,
            current_price,
            target_price,
            product_url,
            recipient=product.get("alert_email"),
        )
    except EmailNotConfigured as exc:
        # Leave alert_sent False so it is retried on the next check
        print(f"WARNING: email alert not sent ({exc})")
        return "Target reached, but email is not configured"
    except Exception as exc:  # SMTP login/network failure
        print(f"WARNING: could not send email alert: {exc}")
        return "Target reached, but alert could not be sent"

    products_collection.update_one({"_id": oid}, {"$set": {"alert_sent": True}})
    return f"Price drop alert emailed to {sent_to}"


@celery_app.task(name="tasks.enqueue_all_products")
def enqueue_all_products():
    count = 0
    for product in products_collection.find({}, {"_id": 1}):
        check_price.delay(str(product["_id"]))
        count += 1
    return f"Scheduled {count} products"
