from datetime import datetime, timedelta, timezone

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from analytics import trend_slope
from database import get_db
from main import app

UTC = timezone.utc
MISSING_ID = "507f1f77bcf86cd799439011"


@pytest.fixture
def db():
    return mongomock.MongoClient()["test_db"]


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_product(client, name="P", target=50000):
    r = client.post(
        "/products",
        json={
            "product_url": "https://www.amazon.in/dp/X",
            "target_price": target,
            "product_name": name,
        },
    )
    return r.json()["id"]


def add_history(db, pid, prices, start=datetime(2026, 10, 1, tzinfo=UTC)):
    db.price_history.insert_many(
        [
            {
                "product_id": ObjectId(pid),
                "price": p,
                "checked_at": start + timedelta(days=i),
            }
            for i, p in enumerate(prices)
        ]
    )


# ---------------------------------------------------------- analytics
def test_trend_slope_direction():
    assert trend_slope([3, 2, 1]) < 0
    assert trend_slope([1, 2, 3]) > 0
    assert trend_slope([5, 5]) is None


# ------------------------------------------------- feature : insights
def test_insights_not_enough_data(client):
    pid = add_product(client)
    body = client.get(f"/products/{pid}/insights").json()
    assert body["recommendation"] == "not_enough_data"


def test_insights_buy_now_at_lowest(client, db):
    pid = add_product(client)
    add_history(db, pid, [100, 100, 100, 100, 100, 80])
    body = client.get(f"/products/{pid}/insights").json()
    assert body["recommendation"] == "buy_now"
    assert body["lowest_price"] == 80


def test_insights_wait_when_above_average(client, db):
    pid = add_product(client)
    add_history(db, pid, [100, 100, 100, 100, 100, 120])
    body = client.get(f"/products/{pid}/insights").json()
    assert body["recommendation"] == "wait"


def test_insights_not_found(client):
    assert client.get(f"/products/{MISSING_ID}/insights").status_code == 404


# ------------------------------------------ feature : drops and events
def test_drops_classified_by_sale_event(client, db):
    pid = add_product(client)
    db.sale_events.insert_one(
        {
            "name": "Test Sale",
            "start_date": datetime(2026, 10, 27, tzinfo=UTC),
            "end_date": datetime(2026, 10, 28, tzinfo=UTC),
        }
    )
    dates = [
        datetime(2026, 10, 25, tzinfo=UTC),
        datetime(2026, 10, 26, tzinfo=UTC),
        datetime(2026, 10, 27, tzinfo=UTC),
        datetime(2026, 11, 10, tzinfo=UTC),
        datetime(2026, 11, 20, tzinfo=UTC),
    ]
    prices = [1000, 1000, 800, 800, 700]
    db.price_history.insert_many(
        [
            {"product_id": ObjectId(pid), "price": p, "checked_at": d}
            for p, d in zip(prices, dates)
        ]
    )
    body = client.get(f"/products/{pid}/drops").json()
    assert [d["classification"] for d in body["drops"]] == [
        "sale_event",
        "standalone",
    ]
    assert body["drops"][0]["sale_event"] == "Test Sale"
    assert body["summary"]["sale_event_drops"] == 1
    assert body["summary"]["standalone_drops"] == 1


def test_sale_event_crud(client):
    r = client.post(
        "/sale-events",
        json={"name": "My Sale", "start_date": "2026-12-01", "end_date": "2026-12-05"},
    )
    assert r.status_code == 201
    event_id = r.json()["id"]
    assert [e["name"] for e in client.get("/sale-events").json()] == ["My Sale"]
    assert client.delete(f"/sale-events/{event_id}").status_code == 200
    assert client.delete(f"/sale-events/{event_id}").status_code == 404


def test_sale_event_end_before_start(client):
    r = client.post(
        "/sale-events",
        json={"name": "Bad", "start_date": "2026-12-05", "end_date": "2026-12-01"},
    )
    assert r.status_code == 400


# ----------------------------------------------- feature : budget
def test_budget_invalid_amount(client):
    assert client.put("/budget", json={"monthly_budget": -1}).status_code == 400


def test_budget_not_set(client):
    assert client.get("/budget").status_code == 404


def test_budget_plan(client, db):
    client.put("/budget", json={"monthly_budget": 60000})

    a = add_product(client, "A")
    b = add_product(client, "B")
    c = add_product(client, "C")
    d = add_product(client, "D")  # never priced

    for pid, current, history in [
        (a, 40000, [60000, 40000]),  # avg 50000 -> 20% deal
        (b, 30000, [32000, 30000]),  # avg 31000 -> ~3% deal
        (c, 20000, [20000, 20000]),  # no deal
    ]:
        db.products.update_one(
            {"_id": ObjectId(pid)}, {"$set": {"current_price": current}}
        )
        add_history(db, pid, history)

    plan = client.get("/budget").json()
    assert [p["product_name"] for p in plan["recommended"]] == ["A"]
    assert plan["budget_left"] == 60000
    assert plan["left_after_recommended"] == 20000
    reasons = {p["product_name"]: p["reason"] for p in plan["skipped"]}
    assert reasons == {"B": "over_budget", "C": "no_deal_yet"}
    assert [p["product_name"] for p in plan["waiting_for_first_price"]] == ["D"]