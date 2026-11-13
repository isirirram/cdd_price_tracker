"""Fills the database with 3 demo products that each have 45 days of fake
price history (including a sale-event dip and a recent standalone drop) and a
demo budget, so insights / drops / budget can be shown before real scraping
works.

Run from the backend folder with MongoDB running:  python seed_demo.py
Safe to re-run: it replaces the previous demo products.
"""
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from database import get_db, init_db

# (name, url, usual price, target price)
DEMO_PRODUCTS = [
    ("Demo Laptop (demo)", "https://www.amazon.in/dp/DEMO001", 55000, 50000),
    ("Demo Headphones (demo)", "https://www.flipkart.com/demo/p/DEMO002", 3000, 2500),
    ("Demo Phone (demo)", "https://www.amazon.in/dp/DEMO003", 18000, 16000),
]


def make_prices(base: float, days: int = 45):
    prices = []
    for days_ago in range(days, -1, -1):
        price = base * (1 + random.uniform(-0.01, 0.01))
        if 20 <= days_ago <= 24:
            price *= 0.88  # dip that falls inside the seeded Diwali window
        if days_ago <= 2:
            price *= 0.93  # recent standalone drop (after the sale window)
        prices.append((days_ago, round(price)))
    return prices


def main():
    random.seed(7)
    db = get_db()
    init_db(db)

    old = list(db.products.find({"product_name": {"$regex": r"\(demo\)$"}}))
    if old:
        ids = [p["_id"] for p in old]
        db.price_history.delete_many({"product_id": {"$in": ids}})
        db.products.delete_many({"_id": {"$in": ids}})

    now = datetime.now(timezone.utc)
    for name, url, base, target in DEMO_PRODUCTS:
        prices = make_prices(base)
        host = urlparse(url).hostname or ""
        site = "amazon" if "amazon" in host else "flipkart"
        result = db.products.insert_one(
            {
                "user_id": "demo-user",
                "product_name": name,
                "product_url": url,
                "site": site,
                "target_price": float(target),
                "current_price": float(prices[-1][1]),
                "alert_sent": False,
                "created_at": now - timedelta(days=45),
            }
        )
        db.price_history.insert_many(
            [
                {
                    "product_id": result.inserted_id,
                    "price": float(price),
                    "checked_at": now - timedelta(days=days_ago),
                }
                for days_ago, price in prices
            ]
        )

    db.budgets.update_one(
        {"user_id": "demo-user"},
        {"$set": {"monthly_budget": 60000.0, "spent_this_month": 0.0, "updated_at": now}},
        upsert=True,
    )
    print("Seeded 3 demo products with 45 days of history and a 60000 budget.")


if __name__ == "__main__":
    main()