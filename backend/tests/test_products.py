from datetime import datetime, timezone

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from database import get_db
from main import app

VALID = {"product_url": "https://shop.example.com/products/test-phone", "target_price": 50000}
MISSING_ID = "507f1f77bcf86cd799439011"  # valid format, not in DB


@pytest.fixture
def db():
    return mongomock.MongoClient(tz_aware=True)["test_db"]


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_add_product(client):
    r = client.post("/products", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["site"] == "shop.example.com"
    assert body["target_price"] == 50000
    assert body["alert_sent"] is False


def test_add_product_negative_price(client):
    r = client.post("/products", json={**VALID, "target_price": -5})
    assert r.status_code == 400


def test_add_product_empty_url(client):
    r = client.post("/products", json={**VALID, "product_url": ""})
    assert r.status_code == 400


def test_list_products(client):
    client.post("/products", json=VALID)
    client.post("/products", json=VALID)
    r = client.get("/products")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_product(client):
    pid = client.post("/products", json=VALID).json()["id"]
    r = client.get(f"/products/{pid}")
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_get_product_not_found(client):
    assert client.get(f"/products/{MISSING_ID}").status_code == 404


def test_get_product_invalid_id(client):
    assert client.get("/products/not-an-id").status_code == 400


def test_history(client, db):
    pid = client.post("/products", json=VALID).json()["id"]
    db.price_history.insert_many(
        [
            {
                "product_id": ObjectId(pid),
                "price": 52000,
                "checked_at": datetime(2026, 11, 10, tzinfo=timezone.utc),
            },
            {
                "product_id": ObjectId(pid),
                "price": 49000,
                "checked_at": datetime(2026, 11, 11, tzinfo=timezone.utc),
            },
        ]
    )
    r = client.get(f"/products/{pid}/history")
    assert r.status_code == 200
    prices = [p["price"] for p in r.json()]
    assert prices == [52000, 49000]  # oldest first, ready for charting


def test_history_not_found(client):
    assert client.get(f"/products/{MISSING_ID}/history").status_code == 404


def test_delete_product(client):
    pid = client.post("/products", json=VALID).json()["id"]
    assert client.delete(f"/products/{pid}").status_code == 200
    assert client.get(f"/products/{pid}").status_code == 404


def test_delete_not_found(client):
    assert client.delete(f"/products/{MISSING_ID}").status_code == 404

# ------------------------------------------------ email + "check now" tests
def test_add_product_with_alert_email(client):
    r = client.post("/products", json={**VALID, "notify_email": "me@example.com"})
    assert r.status_code == 201
    assert r.json()["notify_email"] == "me@example.com"
    assert r.json()["last_error"] is None


def test_add_product_bad_email(client):
    r = client.post("/products", json={**VALID, "notify_email": "not-an-email"})
    assert r.status_code == 400


def test_add_product_queues_first_check(client, monkeypatch):
    import main

    queued = []
    monkeypatch.setattr(main, "queue_price_check", lambda pid: queued.append(pid) or True)
    pid = client.post("/products", json=VALID).json()["id"]
    assert queued == [pid]


def test_check_now_queues_task(client, monkeypatch):
    import main

    monkeypatch.setattr(main, "queue_price_check", lambda pid: True)
    pid = client.post("/products", json=VALID).json()["id"]
    r = client.post(f"/products/{pid}/check")
    assert r.status_code == 202


def test_check_now_without_worker_returns_503(client, monkeypatch):
    import main

    monkeypatch.setattr(main, "queue_price_check", lambda pid: False)
    pid = client.post("/products", json=VALID).json()["id"]
    assert client.post(f"/products/{pid}/check").status_code == 503


def test_check_now_missing_product(client):
    assert client.post(f"/products/{MISSING_ID}/check").status_code == 404


# ------------------------------------- change alert email (from frontend/UI)
def test_add_product_without_notify_email(client):
    r = client.post("/products", json=VALID)
    assert r.status_code == 201
    assert r.json()["notify_email"] is None


def test_update_notify_email_resets_alert(client, db):
    pid = client.post("/products", json=VALID).json()["id"]
    db.products.update_one({"_id": ObjectId(pid)}, {"$set": {"alert_sent": True}})

    r = client.patch(f"/products/{pid}/notify-email", json={"notify_email": "a@b.com"})
    assert r.status_code == 200
    assert r.json()["notify_email"] == "a@b.com"
    assert r.json()["alert_sent"] is False


def test_clear_notify_email(client):
    pid = client.post(
        "/products", json={**VALID, "notify_email": "a@b.com"}
    ).json()["id"]
    r = client.patch(f"/products/{pid}/notify-email", json={"notify_email": None})
    assert r.status_code == 200
    assert r.json()["notify_email"] is None


def test_update_notify_email_missing_product(client):
    r = client.patch(f"/products/{MISSING_ID}/notify-email", json={"notify_email": "a@b.com"})
    assert r.status_code == 404


# ------------------------------------------------ unsupported sites
@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.in/dp/B08L5W4SW6",
        "https://amzn.in/d/abc",
        "https://www.flipkart.com/x/p/itm123",
        "https://dl.flipkart.com/dl/item",
        "https://www.croma.com/x/p/123",
    ],
)
def test_amazon_flipkart_croma_rejected(client, db, url):
    r = client.post("/products", json={**VALID, "product_url": url})
    assert r.status_code == 400
    assert "not supported" in r.json()["detail"]
    assert db.products.count_documents({}) == 0


def test_lookalike_domain_is_not_blocked(client):
    # "notamazon.example" must not be treated as Amazon
    r = client.post("/products", json={**VALID, "product_url": "https://notamazon.example/products/x"})
    assert r.status_code == 201


# --------------------------------------------------- telegram chat id
def test_add_product_with_telegram_chat(client):
    r = client.post("/products", json={**VALID, "telegram_chat_id": "-1001234567890"})
    assert r.status_code == 201
    assert r.json()["telegram_chat_id"] == "-1001234567890"


@pytest.mark.parametrize("bad", ["abc", "12", "@no", "1; DROP"])
def test_bad_telegram_chat_rejected(client, bad):
    r = client.post("/products", json={**VALID, "telegram_chat_id": bad})
    assert r.status_code == 400


# ------------------------------------------------- price comparison
SHOPIFY_B = "https://store-b.example.com/products/test-phone"
WOO_C = "https://store-c.example.com/product/test-phone/"


def test_compare_single_store(client):
    pid = client.post("/products", json=VALID).json()["id"]
    r = client.get(f"/products/{pid}/compare")
    assert r.status_code == 200
    body = r.json()
    assert body["store_count"] == 1
    assert body["cheapest_id"] is None  # no price checked yet


def test_compare_adds_stores_and_finds_cheapest(client, db):
    main = client.post(
        "/products", json={**VALID, "notify_email": "me@example.com"}
    ).json()
    b = client.post(f"/products/{main['id']}/compare", json={"product_url": SHOPIFY_B})
    assert b.status_code == 201
    # adding from a linked product joins the same group
    c = client.post(f"/products/{b.json()['id']}/compare", json={"product_url": WOO_C})
    assert c.status_code == 201
    assert b.json()["group_id"] == c.json()["group_id"] == main["id"]
    # alert settings are copied to the new store
    assert c.json()["notify_email"] == "me@example.com"
    assert c.json()["target_price"] == main["target_price"]

    for pid, price in ((main["id"], 52000), (b.json()["id"], 49999), (c.json()["id"], 51000)):
        db.products.update_one({"_id": ObjectId(pid)}, {"$set": {"current_price": price}})

    body = client.get(f"/products/{c.json()['id']}/compare").json()
    assert body["store_count"] == 3
    assert body["cheapest_id"] == b.json()["id"]
    assert body["cheapest_site"] == "store-b.example.com"
    assert body["max_saving"] == 2001
    assert [o["current_price"] for o in body["offers"]] == [49999, 51000, 52000]
    assert [o["platform"] for o in body["offers"]] == ["shopify", "woocommerce", "shopify"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.amazon.in/dp/B08L5W4SW6",
        "https://example.com/some/page",
        "http://127.0.0.1:8001/products/product-001",
    ],
)
def test_compare_only_shopify_and_woocommerce(client, url):
    pid = client.post("/products", json=VALID).json()["id"]
    r = client.post(f"/products/{pid}/compare", json={"product_url": url})
    assert r.status_code == 400


def test_compare_duplicate_link_rejected(client):
    pid = client.post("/products", json=VALID).json()["id"]
    assert client.post(f"/products/{pid}/compare", json={"product_url": SHOPIFY_B}).status_code == 201
    assert client.post(f"/products/{pid}/compare", json={"product_url": SHOPIFY_B}).status_code == 409
    assert client.post(f"/products/{pid}/compare", json={"product_url": VALID["product_url"]}).status_code == 409


def test_compare_missing_product(client):
    assert client.get(f"/products/{MISSING_ID}/compare").status_code == 404


def test_old_unsupported_products_removed_on_startup(db):
    from database import remove_unsupported_products

    now = datetime.now(timezone.utc)
    old = db.products.insert_one(
        {"product_url": "https://www.amazon.in/dp/X", "site": "amazon", "created_at": now}
    ).inserted_id
    keep = db.products.insert_one(
        {"product_url": "https://shop.example.com/products/x", "site": "x", "created_at": now}
    ).inserted_id
    db.price_history.insert_one({"product_id": old, "price": 1.0, "checked_at": now})

    assert remove_unsupported_products(db) == 1
    assert db.products.find_one({"_id": old}) is None
    assert db.products.find_one({"_id": keep}) is not None
    assert db.price_history.count_documents({}) == 0


def test_dates_are_sent_with_utc_offset(client):
    """Browsers treat a date without an offset as local time, which showed
    every 'Last checked' time 5.5 hours early in India."""
    pid = client.post("/products", json=VALID).json()["id"]
    body = client.get(f"/products/{pid}").json()  # read back from MongoDB
    assert body["created_at"].endswith(("+00:00", "Z"))
