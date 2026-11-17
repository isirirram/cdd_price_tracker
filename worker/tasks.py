from datetime import datetime, timezone
from bson import ObjectId

from celery_app import celery_app
from database import (
    products_collection,
    price_history_collection
)
from scraper_adapter import get_scraper_result
from notifications import resolve_recipient, send_email_alert


@celery_app.task(name="tasks.check_price")
def check_price(product_id, simulated_price=None):

    # Find the product
    product = products_collection.find_one({
        "_id": ObjectId(product_id)
    })

    if not product:
        return "Product not found"

    product_name = product["product_name"]
    product_url = product["product_url"]
    target_price = float(product["target_price"])

    # Get current price and retention permission
    if simulated_price is not None:
        current_price = float(simulated_price)
        allow_history = False
        checked_at = datetime.now(timezone.utc)

    else:
        result = get_scraper_result(product_url)

        current_price = float(result.current_price)
        checked_at = result.checked_at

        # Replace the "Pending first price check" placeholder with the real name
        if result.product_name and result.product_name != product_name:
            product_name = result.product_name
            products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"product_name": product_name}}
            )

        policy = result.cache_policy

        if policy.price_ttl_seconds <= 0:
            raise ValueError("Invalid price cache TTL")

        if policy.metadata_ttl_seconds <= 0:
            raise ValueError("Invalid metadata cache TTL")

        allow_history = policy.allow_historical_storage

    if current_price <= 0:
        raise ValueError("Invalid product price")

    # Save history only when permitted
    if allow_history:
        price_history_collection.insert_one({
            "product_id": ObjectId(product_id),
            "price": current_price,
            "checked_at": checked_at
        })

    # Update current price
    products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"current_price": current_price}}
    )

    alert_sent = product.get("alert_sent", False)

    # Check target price
    if current_price <= target_price:

        if not alert_sent:
            to_email = resolve_recipient(product)

            if not to_email:
                # No address for this product and no ALERT_EMAIL_TO fallback.
                # alert_sent stays False, so adding an email later still works.
                print(f"WARNING: no alert email set for product {product_id}")
                return "Target reached, but no email address is set"

            try:
                send_email_alert(
                    to_email=to_email,
                    product_name=product_name,
                    product_url=product_url,
                    current_price=current_price,
                    target_price=target_price,
                )
            except Exception as exc:
                # Don't crash the whole price check if SMTP isn't set up or fails;
                # alert_sent stays False so it retries on the next check.
                print(f"WARNING: could not send email alert: {exc}")
                return "Target reached, but alert email could not be sent"

            products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"alert_sent": True}}
            )

            return f"Price drop alert emailed to {to_email}"

        return "Alert already sent"

    else:
        products_collection.update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {"alert_sent": False}}
        )

    return "Price checked successfully!"


@celery_app.task(name="tasks.enqueue_all_products")
def enqueue_all_products():

    products = products_collection.find(
        {},
        {"_id": 1}
    )

    count = 0

    for product in products:
        check_price.delay(str(product["_id"]))
        count += 1

    return f"Scheduled {count} products"