from datetime import datetime, timezone

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from database import get_db
from main import app

VALID = {"product_url": "https://www.amazon.in/dp/TEST123", "target_price": 50000}
MISSING_ID = "507f1f77bcf86cd799439011"  # valid format, not in DB


@pytest.fixture
def db():
    return mongomock.MongoClient()["test_db"]


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_add_product(client):
    r = client.post("/products", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["site"] == "amazon"
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