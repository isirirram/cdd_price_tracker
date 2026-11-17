from datetime import datetime, timezone
from types import SimpleNamespace

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
    for var in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO"):
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
                "alert_email": email,
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
    monkeypatch.setattr(
        tasks, "send_email_alert", lambda *a, **k: sent.append(k["recipient"]) or k["recipient"]
    )

    assert "emailed to buyer@example.com" in tasks.check_price(pid, simulated_price=900)
    assert tasks.check_price(pid, simulated_price=850) == "Alert already sent"
    assert sent == ["buyer@example.com"]
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is True


def test_alert_rearms_when_price_goes_back_up(monkeypatch):
    pid = add_product(target=1000, alert_sent=True)
    tasks.check_price(pid, simulated_price=1200)
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is False


def test_missing_smtp_config_does_not_crash():
    pid = add_product(target=1000)
    assert tasks.check_price(pid, simulated_price=900) == "Target reached, but email is not configured"
    # still False so the alert is retried once SMTP is configured
    assert products_collection.find_one({"_id": ObjectId(pid)})["alert_sent"] is False


def test_invalid_and_missing_ids():
    assert tasks.check_price("not-an-id") == "Invalid product id"
    assert tasks.check_price("507f1f77bcf86cd799439011") == "Product not found"


def test_email_message_and_recipient_fallback(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "team@example.com")
    assert notifications.resolve_recipient(None) == "team@example.com"
    assert notifications.resolve_recipient("me@example.com") == "me@example.com"

    msg = notifications.build_message("bot@x.com", "me@x.com", "Headphones", 900, 1000, "http://x")
    assert "Headphones" in msg["Subject"]
    assert "₹100.00" in msg.get_content()


def test_send_email_uses_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "bot@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    calls = SimpleNamespace(sent=None, tls=False)

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("smtp.example.com", 587)
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def starttls(self, context):
            calls.tls = True
        def login(self, user, password):
            assert password == "secret"
        def send_message(self, msg):
            calls.sent = msg

    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    to = notifications.send_email_alert("Headphones", 900, 1000, "http://x", "me@example.com")
    assert to == "me@example.com"
    assert calls.tls and calls.sent["To"] == "me@example.com"
