from datetime import datetime, timezone

import pytest
from bson import ObjectId

import notifications
import tasks
from database import price_history_collection, products_collection
from scraper.models import CachePolicy, ScraperResult, SourceCategory


@pytest.fixture(autouse=True)
def clean_db(monkeypatch):
    products_collection.delete_many({})
    price_history_collection.delete_many({})
    for var in (
        "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


def add_product(target=1000.0, alert_sent=False, email="buyer@example.com"):
    return str(
        products_collection.insert_one(
            {
                "user_id": "demo-user",
                "product_name": "Pending first price check",
                "product_url": "http://127.0.0.1:8001/products/product-001",
                "site": "other",
                "target_price": target,
                "current_price": None,
                "alert_sent": alert_sent,
                "notify_email": email,
                "created_at": datetime.now(timezone.utc),
            }
        ).inserted_id
    )


def fake_result(price, allow_history=True):
    return ScraperResult(
        success=True,
        product_name="Demo Headphones",
        current_price=price,
        site="local_store",
        product_url="http://127.0.0.1:8001/products/product-001",
        source_category=SourceCategory.CONTROLLED_DEMO_STORE,
        is_commercial_store=False,
        cache_policy=CachePolicy(
            price_ttl_seconds=60, metadata_ttl_seconds=60, allow_historical_storage=allow_history
        ),
    )


def test_tasks_module_imports():
    # Regression test: tasks.py used to import a deleted notifications module
    assert tasks.check_price.name == "tasks.check_price"


def test_price_above_target_saves_history_and_name(monkeypatch):
    pid = add_product(target=1000)
    monkeypatch.setattr(tasks, "get_scraper_result", lambda url: fake_result(1499))

    assert tasks.check_price(pid) == "Price checked successfully!"
    doc = products_collection.find_one({"_id": ObjectId(pid)})
    assert doc["current_price"] == 1499
    assert doc["product_name"] == "Demo Headphones"
    assert doc["last_error"] is None
    assert price_history_collection.count_documents({"product_id": ObjectId(pid)}) == 1


def test_history_not_saved_when_licence_forbids(monkeypatch):
    pid = add_product()
    monkeypatch.setattr(tasks, "get_scraper_result", lambda url: fake_result(1499, allow_history=False))
    tasks.check_price(pid)
    assert price_history_collection.count_documents({}) == 0


def test_scrape_failure_is_recorded(monkeypatch):
    pid = add_product()

    def boom(url):
        raise RuntimeError("Scraping failed: credentials missing")

    monkeypatch.setattr(tasks, "get_scraper_result", boom)
    assert tasks.check_price(pid).startswith("Price check failed")
    doc = products_collection.find_one({"_id": ObjectId(pid)})
    assert "credentials missing" in doc["last_error"]
    assert doc["current_price"] is None


def test_alert_sent_once_when_target_reached(monkeypatch):
    pid = add_product(target=1000)
    sent = []
    monkeypatch.setattr(notifications, "send_email_alert", lambda **k: sent.append(k["to_email"]))

    assert tasks.check_price(pid, simulated_price=900) == (
        "Price drop alert sent via email to buyer@example.com"
    )
    assert tasks.check_price(pid, simulated_price=850) == "Alert already sent"
    assert sent == ["buyer@example.com"]
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is True


def test_concurrent_check_does_not_send_duplicate(monkeypatch):
    """Two checks read the product before either one marks the alert as sent.
    Only the one that wins the atomic claim may send."""
    pid = add_product(target=1000)
    sent = []
    monkeypatch.setattr(notifications, "send_email_alert", lambda **k: sent.append(1))

    # Check B starts while check A is sending: by then A has already claimed it.
    def send_and_race(**k):
        sent.append(1)
        assert tasks.check_price(pid, simulated_price=880) == "Alert already sent"

    monkeypatch.setattr(notifications, "send_email_alert", send_and_race)
    assert tasks.check_price(pid, simulated_price=900).startswith("Price drop alert sent")
    assert sent == [1]


def test_alert_rearms_when_price_goes_back_up(monkeypatch):
    pid = add_product(target=1000, alert_sent=True)
    tasks.check_price(pid, simulated_price=1200)
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is False


def test_no_recipient_does_not_crash():
    pid = add_product(target=1000, email=None)
    result = tasks.check_price(pid, simulated_price=900)
    assert result == "Target reached, but alert not sent: no email address is set"
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is False


def test_missing_smtp_config_does_not_crash():
    pid = add_product(target=1000)
    result = tasks.check_price(pid, simulated_price=900)
    assert result == "Target reached, but alert not sent: email is not configured"
    # back to False so the alert is retried once SMTP is configured
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is False


def test_telegram_and_email_both_sent(monkeypatch):
    pid = add_product(target=1000)
    products_collection.update_one(
        {"_id": ObjectId(pid)}, {"$set": {"telegram_chat_id": "123456789"}}
    )
    calls = []
    monkeypatch.setattr(notifications, "send_email_alert", lambda **k: calls.append("email"))
    monkeypatch.setattr(
        notifications, "send_telegram_alert", lambda **k: calls.append(("tg", k["chat_id"]))
    )
    result = tasks.check_price(pid, simulated_price=900)
    assert result == "Price drop alert sent via email to buyer@example.com, Telegram"
    assert calls == ["email", ("tg", "123456789")]


def test_telegram_alone_is_enough(monkeypatch):
    """Email not configured, Telegram works -> alert counts as sent."""
    pid = add_product(target=1000)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "555")
    monkeypatch.setattr(notifications, "send_telegram_alert", lambda **k: None)
    assert tasks.check_price(pid, simulated_price=900) == "Price drop alert sent via Telegram"
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is True


def test_invalid_and_missing_ids():
    assert tasks.check_price("not-an-id") == "Invalid product id"
    assert tasks.check_price("507f1f77bcf86cd799439011") == "Product not found"


def test_scraped_metadata_is_saved_on_product(monkeypatch):
    pid = add_product(target=1000)
    result = fake_result(1499)
    result.image_url = "https://cdn.example.com/headphones.jpg"
    monkeypatch.setattr(tasks, "get_scraper_result", lambda url: result)

    tasks.check_price(pid)

    doc = products_collection.find_one({"_id": ObjectId(pid)})
    assert doc["product_name"] == "Demo Headphones"
    assert doc["current_price"] == 1499
    assert doc["image_url"] == "https://cdn.example.com/headphones.jpg"
    assert doc["site"] == "Demo Store"
    assert doc["last_error"] is None
    assert doc["last_checked_at"] is not None


def test_missing_image_does_not_wipe_saved_image(monkeypatch):
    pid = add_product(target=1000)
    products_collection.update_one(
        {"_id": ObjectId(pid)}, {"$set": {"image_url": "https://cdn.example.com/old.jpg"}}
    )
    monkeypatch.setattr(tasks, "get_scraper_result", lambda url: fake_result(1499))

    tasks.check_price(pid)

    doc = products_collection.find_one({"_id": ObjectId(pid)})
    assert doc["image_url"] == "https://cdn.example.com/old.jpg"


def test_platform_site_is_shown_as_store_domain():
    assert tasks._website_name("shopify", "https://www.boat-lifestyle.com/products/x") == "boat-lifestyle.com"
    assert tasks._website_name("generic", "https://shop.example.in/item/1") == "shop.example.in"
    assert tasks._website_name("local_store", "http://127.0.0.1:8001/products/product-001") == "Demo Store"


def test_failed_scrape_keeps_old_details_and_saves_error(monkeypatch):
    pid = add_product(target=1000)
    products_collection.update_one(
        {"_id": ObjectId(pid)},
        {"$set": {"current_price": 1200.0, "image_url": "https://cdn.example.com/a.jpg"}},
    )

    def boom(url):
        raise RuntimeError("Scraping failed: blocked")

    monkeypatch.setattr(tasks, "get_scraper_result", boom)
    assert tasks.check_price(pid).startswith("Price check failed")

    doc = products_collection.find_one({"_id": ObjectId(pid)})
    assert doc["current_price"] == 1200.0
    assert doc["image_url"] == "https://cdn.example.com/a.jpg"
    assert doc["last_error"] == "Scraping failed: blocked"
