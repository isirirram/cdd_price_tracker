"""Product logic shared by the REST endpoints (main.py) and the chatbot (chatbot.py)."""

from datetime import datetime, timezone
from urllib.parse import urlparse

from models import ProductCreate


def detect_site(url: str) -> str:
    host = urlparse(url).hostname or ""
    if "amazon" in host:
        return "amazon"
    if "flipkart" in host:
        return "flipkart"
    return "other"


def create_product(db, payload: ProductCreate) -> dict:
    """Insert a new tracked product and return the stored document."""
    url = str(payload.product_url)
    doc = {
        "user_id": payload.user_id,
        "product_name": payload.product_name or "Pending first price check",
        "product_url": url,
        "site": detect_site(url),
        "target_price": payload.target_price,
        "current_price": None,
        "alert_sent": False,
        "notify_email": str(payload.notify_email) if payload.notify_email else None,
        "image_url": None,  # filled in by the worker after the first scrape
        "created_at": datetime.now(timezone.utc),
    }
    result = db.products.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc
