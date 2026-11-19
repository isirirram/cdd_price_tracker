import json
from datetime import datetime, timedelta, timezone

import mongomock
import pytest
from fastapi.testclient import TestClient

import chatbot
import task_queue
from database import get_db
from main import app

DEMO_URL = "http://127.0.0.1:8001/products/product-001"


@pytest.fixture
def db():
    return mongomock.MongoClient(tz_aware=True)["test_db"]


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(task_queue, "queue_price_check", lambda pid: True)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_with_history(db, name, prices, target):
    now = datetime.now(timezone.utc)
    pid = db.products.insert_one(
        {
            "user_id": "demo-user",
            "product_name": name,
            "product_url": DEMO_URL,
            "site": "other",
            "target_price": target,
            "current_price": prices[-1],
            "alert_sent": False,
            "created_at": now,
        }
    ).inserted_id
    db.price_history.insert_many(
        [
            {"product_id": pid, "price": p, "checked_at": now - timedelta(days=len(prices) - i)}
            for i, p in enumerate(prices)
        ]
    )
    return str(pid)


def say(client, message, history=None):
    r = client.post("/chat", json={"message": message, "history": history or []})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------ offline mode
def test_status_offline(client):
    assert client.get("/chat/status").json() == {"mode": "offline"}


def test_add_product_from_sentence(client, db):
    body = say(client, f"Track {DEMO_URL} under ₹1,200 and email me at siri@example.com")
    assert body["mode"] == "offline"
    assert "Now tracking" in body["reply"]
    assert body["actions"][0]["type"] == "product_added"

    doc = db.products.find_one()
    assert doc["target_price"] == 1200
    assert doc["notify_email"] == "siri@example.com"
    assert doc["product_url"] == DEMO_URL


def test_add_product_with_k_suffix(client, db):
    say(client, f"watch {DEMO_URL} below 1.5k")
    assert db.products.find_one()["target_price"] == 1500


def test_add_product_asks_for_price(client, db):
    body = say(client, f"track this {DEMO_URL}")
    assert "target price" in body["reply"]
    assert db.products.count_documents({}) == 0


def test_buy_advice_by_name(client, db):
    add_with_history(db, "Demo Wireless Headphones", [1500, 1490, 1510, 1480, 1500, 1200], 1300)
    add_with_history(db, "Demo Gaming Keyboard", [4000, 4000, 4000, 4000, 4000, 4000], 3500)
    reply = say(client, "should I buy the headphones now?")["reply"]
    assert "Headphones" in reply
    assert "good time to buy" in reply
    assert "not a guarantee" in reply


def test_buy_advice_not_enough_data(client, db):
    add_with_history(db, "Demo Mouse", [900, 899], 800)
    reply = say(client, "is the mouse worth buying?")["reply"]
    assert "enough price history" in reply


def test_ambiguous_advice_asks_which(client, db):
    add_with_history(db, "Demo Mouse", [900], 800)
    add_with_history(db, "Demo Webcam", [5000], 4000)
    reply = say(client, "should I buy it?")["reply"]
    assert "Which product" in reply


def test_list_products(client, db):
    add_with_history(db, "Demo Mouse", [900], 800)
    assert "Demo Mouse" in say(client, "show my products")["reply"]


def test_budget(client, db):
    add_with_history(db, "Demo Mouse", [1000, 1000, 1000, 800], 850)
    client.put("/budget", json={"monthly_budget": 5000})
    reply = say(client, "what can I afford this month?")["reply"]
    assert "Demo Mouse" in reply


def test_budget_not_set(client):
    assert "No monthly budget" in say(client, "what fits my budget?")["reply"]


def test_help_message(client):
    assert "I can help with" in say(client, "hello")["reply"]


def test_empty_message_rejected(client):
    assert client.post("/chat", json={"message": ""}).status_code == 400


def test_user_cannot_see_other_users_products(db):
    db.products.insert_one(
        {"user_id": "someone-else", "product_name": "Secret", "target_price": 1, "created_at": datetime.now(timezone.utc)}
    )
    assert chatbot.ChatTools(db, "demo-user").list_products()["count"] == 0


# ---------------------------------------------------------------- AI mode
def fake_llm(script):
    """Returns a call_llm replacement that plays back `script` and records messages."""
    calls = []

    def _call(messages):
        calls.append([dict(m) for m in messages])
        return script[len(calls) - 1]

    return _call, calls


def tool_call(name, args, call_id="call_1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
        ],
    }


def test_ai_mode_runs_tools_and_answers(client, db, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    pid = add_with_history(db, "Demo Headphones", [1500, 1490, 1510, 1480, 1500, 1200], 1300)
    call, calls = fake_llm(
        [
            tool_call("list_products", {}),
            tool_call("get_buy_advice", {"product_id": pid}, "call_2"),
            {"role": "assistant", "content": "Buy now - it's the lowest price so far."},
        ]
    )
    monkeypatch.setattr(chatbot, "call_llm", call)

    body = say(client, "should I buy the headphones?", [{"role": "user", "content": "hi"}])
    assert body == {"reply": "Buy now - it's the lowest price so far.", "actions": [], "mode": "ai"}

    # the LLM got the real data back from our tools
    tool_msgs = [m for m in calls[-1] if m["role"] == "tool"]
    assert "Demo Headphones" in tool_msgs[0]["content"]
    assert '"buy_now"' in tool_msgs[1]["content"]
    assert calls[0][1] == {"role": "user", "content": "hi"}  # history passed through


def test_ai_mode_adds_product(client, db, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    call, _ = fake_llm(
        [
            tool_call("add_product", {"product_url": DEMO_URL, "target_price": 999}),
            {"role": "assistant", "content": "Added!"},
        ]
    )
    monkeypatch.setattr(chatbot, "call_llm", call)
    body = say(client, f"track {DEMO_URL} under 999")
    assert body["actions"][0]["type"] == "product_added"
    assert db.products.find_one()["target_price"] == 999


def test_ai_mode_bad_tool_input_is_reported_not_crashing(client, db, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    call, calls = fake_llm(
        [
            tool_call("add_product", {"product_url": "not a url", "target_price": -1}),
            {"role": "assistant", "content": "That link doesn't look right."},
        ]
    )
    monkeypatch.setattr(chatbot, "call_llm", call)
    say(client, "track my thing")
    assert "Could not add product" in calls[-1][-1]["content"]
    assert db.products.count_documents({}) == 0


def test_ai_failure_falls_back_to_offline(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    def broken(messages):
        raise ConnectionError("no internet")

    monkeypatch.setattr(chatbot, "call_llm", broken)
    body = say(client, "hello")
    assert body["mode"] == "offline"
    assert "I can help with" in body["reply"]


def test_call_llm_request_format(monkeypatch):
    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return FakeResponse()

    monkeypatch.setenv("LLM_API_KEY", "abc")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setattr(chatbot.httpx, "post", fake_post)
    assert chatbot.call_llm([{"role": "user", "content": "hi"}])["content"] == "ok"
    assert sent["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer abc"
    assert sent["body"]["model"] == chatbot.DEFAULT_MODEL
    assert {t["function"]["name"] for t in sent["body"]["tools"]} >= {"get_buy_advice", "add_product"}
