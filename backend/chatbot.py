"""Price assistant chatbot.

Two jobs:
  1. "Should I buy now?" - explains the insights / drop report / budget plan
     for the user's tracked products in plain language.
  2. Add products from a sentence - "track http://... under 1500, email me@x.com"

How it works
------------
If LLM_API_KEY is set, the message goes to an LLM (any OpenAI-compatible API:
Groq by default, or Gemini / OpenAI etc. via LLM_BASE_URL + LLM_MODEL). The LLM
can't see the database directly; it can only call the TOOLS below, which run
our own Python code. So every price it mentions comes from our data.

If there is no key, or the LLM call fails (e.g. no internet at the expo),
a simple rule-based fallback answers instead, so the bot always works.
"""

import json
import os
import re

import httpx
from bson import ObjectId
from bson.errors import InvalidId
from pydantic import ValidationError

import task_queue
from analytics import build_budget_plan, build_drop_report, build_insights
from models import ProductCreate
from product_service import UnsupportedSiteError, create_product

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
MAX_TOOL_ROUNDS = 5
MAX_HISTORY = 10

SYSTEM_PROMPT = """You are the assistant inside "Smart Price Tracker", a price-tracking app for Indian shoppers.
You help with two things:
1. Advice on whether to buy a tracked product now or wait, and what fits the user's monthly budget.
2. Adding products to track when the user gives a product URL and a target price.

Rules:
- Only state prices, trends and numbers that come from tool results. Never invent prices or products.
- To talk about a product, call list_products first to find its id, then get_buy_advice.
- Prices are in Indian Rupees; write them like ₹1,499.
- To add a product you need a URL and a target price. The alert email is optional. Ask if the URL or price is missing.
- Buy advice is a statistical hint from past prices, not a guarantee; say so briefly when you give a recommendation.
- Keep answers short and friendly: 2-5 sentences or a short list."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "List the user's tracked products with id, name, current price, target price and status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_buy_advice",
            "description": "Buy-now-or-wait analysis for one product: recommendation, reason, lowest/average price, trend, active sale event and past price drops.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_budget_plan",
            "description": "Which tracked products are good deals that fit in the user's remaining monthly budget.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_product",
            "description": "Start tracking a product. Only call when the user gave a product URL and a target price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_url": {"type": "string", "description": "Full http(s) product URL"},
                    "target_price": {"type": "number", "description": "Alert when price is at or below this, in INR"},
                    "notify_email": {"type": "string", "description": "Optional email for the price-drop alert"},
                },
                "required": ["product_url", "target_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_price_now",
            "description": "Ask the price checker to fetch a fresh price for one product right now.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
]


def inr(value) -> str:
    return f"₹{value:,.0f}" if value is not None else "not checked yet"


# ------------------------------------------------------------------ tools
class ChatTools:
    """The only things the bot is allowed to do. Each returns a JSON-able dict."""

    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id
        self.actions = []  # told to the frontend, e.g. so it can refresh the product list

    def _products(self):
        return list(self.db.products.find({"user_id": self.user_id}).sort("created_at", -1))

    def _product(self, product_id):
        try:
            oid = ObjectId(product_id)
        except (InvalidId, TypeError):
            return None
        return self.db.products.find_one({"_id": oid, "user_id": self.user_id})

    def list_products(self):
        items = []
        for p in self._products():
            current, target = p.get("current_price"), p["target_price"]
            if current is None:
                status = "waiting for first price check"
            elif current <= target:
                status = "at or below target"
            else:
                status = "above target"
            items.append(
                {
                    "id": str(p["_id"]),
                    "name": p.get("product_name"),
                    "site": p.get("site"),
                    "current_price": current,
                    "target_price": target,
                    "status": status,
                    "last_error": p.get("last_error"),
                }
            )
        return {"products": items, "count": len(items)}

    def get_buy_advice(self, product_id):
        product = self._product(product_id)
        if not product:
            return {"error": "No tracked product with that id. Call list_products first."}
        history = list(self.db.price_history.find({"product_id": product["_id"]}))
        events = list(self.db.sale_events.find())
        insights = build_insights(history, events)
        drops = build_drop_report(history, events)
        return {
            "product_name": product.get("product_name"),
            "target_price": product["target_price"],
            "insights": insights,
            "drop_summary": drops["summary"],
        }

    def get_budget_plan(self):
        budget = self.db.budgets.find_one({"user_id": self.user_id})
        if not budget:
            return {"error": "No monthly budget set yet. The user can set one on the Budget Tracker page."}
        products = self._products()
        ids = [p["_id"] for p in products]
        averages = {
            row["_id"]: row["avg"]
            for row in self.db.price_history.aggregate(
                [
                    {"$match": {"product_id": {"$in": ids}}},
                    {"$group": {"_id": "$product_id", "avg": {"$avg": "$price"}}},
                ]
            )
        }
        return build_budget_plan(
            budget["monthly_budget"], budget.get("spent_this_month", 0.0), products, averages
        )

    def add_product(self, product_url, target_price, notify_email=None):
        try:
            payload = ProductCreate(
                product_url=product_url,
                target_price=target_price,
                notify_email=notify_email or None,
                user_id=self.user_id,
            )
        except ValidationError as exc:
            problems = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors())
            return {"error": f"Could not add product ({problems})"}
        try:
            doc = create_product(self.db, payload)
        except UnsupportedSiteError as exc:
            return {"error": str(exc)}
        queued = task_queue.queue_price_check(str(doc["_id"]))
        self.actions.append({"type": "product_added", "product_id": str(doc["_id"])})
        return {
            "added": True,
            "product_id": str(doc["_id"]),
            "product_url": doc["product_url"],
            "target_price": doc["target_price"],
            "notify_email": doc["notify_email"],
            "first_price_check_started": queued,
        }

    def check_price_now(self, product_id):
        product = self._product(product_id)
        if not product:
            return {"error": "No tracked product with that id. Call list_products first."}
        if not task_queue.queue_price_check(str(product["_id"])):
            return {"error": "The price checker (worker) is not running right now."}
        self.actions.append({"type": "price_check_queued", "product_id": product_id})
        return {"queued": True, "product_name": product.get("product_name")}

    def run(self, name, arguments):
        func = {
            "list_products": self.list_products,
            "get_buy_advice": self.get_buy_advice,
            "get_budget_plan": self.get_budget_plan,
            "add_product": self.add_product,
            "check_price_now": self.check_price_now,
        }.get(name)
        if func is None:
            return {"error": f"Unknown tool {name}"}
        try:
            return func(**arguments)
        except TypeError as exc:  # LLM sent wrong arguments
            return {"error": f"Bad arguments for {name}: {exc}"}


# -------------------------------------------------------------- LLM mode
def llm_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY", "").strip())


def call_llm(messages: list) -> dict:
    """One call to an OpenAI-compatible /chat/completions endpoint. Returns the message."""
    base = os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    resp = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY', '').strip()}"},
        json={
            "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.2,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


def chat_with_llm(tools: ChatTools, message: str, history: list) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": message}]

    for _ in range(MAX_TOOL_ROUNDS):
        reply = call_llm(messages)
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            return (reply.get("content") or "").strip() or "Sorry, I couldn't come up with an answer."

        messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": tool_calls})
        for call in tool_calls:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run(call["function"]["name"], args)
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, default=str)}
            )

    return "Sorry, that took too many steps. Could you ask in a simpler way?"


# --------------------------------------------------------- offline mode
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
PRICE_RE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k)?\b", re.IGNORECASE)

ADVICE_TEXT = {
    "buy_now": "👍 Looks like a good time to buy.",
    "wait": "⏳ I'd wait a bit.",
    "neutral": "😐 The price is about normal - no strong signal either way.",
    "not_enough_data": "I don't have enough price history yet to judge.",
}

HELP_TEXT = (
    "I can help with:\n"
    "• \"Should I buy the headphones now?\"\n"
    "• \"What fits in my budget?\"\n"
    "• \"Show my products\"\n"
    "• \"Track http://127.0.0.1:8001/products/product-002 under 2000, email me@example.com\""
)


def parse_price(text: str):
    for match in PRICE_RE.finditer(text):
        value = float(match.group(1).replace(",", ""))
        if match.group(2):
            value *= 1000
        if value > 0:
            return value
    return None


def find_product(products: list, text: str):
    """Pick the tracked product whose name shares the most words with the message."""
    words = set(re.findall(r"[a-z0-9]{3,}", text.lower())) - {"the", "should", "buy", "now", "price", "and", "for"}
    best, best_score = None, 0
    for p in products:
        name_words = set(re.findall(r"[a-z0-9]{3,}", (p.get("name") or "").lower()))
        score = len(words & name_words)
        if score > best_score:
            best, best_score = p, score
    return best


def format_advice(data: dict) -> str:
    ins = data["insights"]
    lines = [f"**{data['product_name']}**", ADVICE_TEXT.get(ins["recommendation"], "")]
    lines.append(ins.get("reason", ""))
    if ins["recommendation"] != "not_enough_data":
        lines.append(
            f"Now {inr(ins['current_price'])} · lowest {inr(ins['lowest_price'])} · "
            f"average {inr(ins['average_price'])} · your target {inr(data['target_price'])}"
        )
    if ins.get("sale_note"):
        lines.append(ins["sale_note"])
    summary = data["drop_summary"]
    if summary["sale_event_drops"] or summary["standalone_drops"]:
        lines.append(
            f"Past drops: {summary['sale_event_drops']} during sale events, "
            f"{summary['standalone_drops']} outside them."
        )
    lines.append(f"_{ins['disclaimer']}_")
    return "\n".join(line for line in lines if line)


def offline_reply(tools: ChatTools, message: str) -> str:
    text = message.lower()
    url_match = URL_RE.search(message)

    # Job 2: add a product from a sentence
    if url_match:
        url = url_match.group(0).rstrip(".,)")
        rest = message.replace(url_match.group(0), " ")
        email_match = EMAIL_RE.search(rest)
        if email_match:
            rest = rest.replace(email_match.group(0), " ")
        price = parse_price(rest)
        if price is None:
            return "Got the link! What target price should I alert you at? e.g. \"under 1500\""
        result = tools.add_product(url, price, email_match.group(0) if email_match else None)
        if "error" in result:
            return result["error"]
        reply = f"✅ Now tracking that product. I'll alert you when it drops to {inr(price)} or below"
        reply += f" (email to {result['notify_email']})." if result["notify_email"] else "."
        if result["first_price_check_started"]:
            reply += " Fetching its current price now."
        return reply

    products = tools.list_products()["products"]

    if any(w in text for w in ("budget", "afford", "spend")):
        plan = tools.get_budget_plan()
        if "error" in plan:
            return plan["error"]
        if not plan["recommended"]:
            return f"You have {inr(plan['budget_left'])} left this month, but none of your products is a good deal that fits right now."
        picks = "\n".join(
            f"• {p['product_name']} - {inr(p['current_price'])} ({p['deal_score_percent']}% below its average)"
            for p in plan["recommended"]
        )
        return (
            f"You have {inr(plan['budget_left'])} left this month. Good deals that fit:\n{picks}\n"
            f"That leaves {inr(plan['left_after_recommended'])}."
        )

    if any(w in text for w in ("list", "my products", "tracking", "show")):
        if not products:
            return "You aren't tracking anything yet. Send me a product link and a target price!"
        return "Here's what you're tracking:\n" + "\n".join(
            f"• {p['name']}: {inr(p['current_price'])} (target {inr(p['target_price'])}, {p['status']})"
            for p in products
        )

    named = find_product(products, message)
    # With only one product, "should I buy it?" obviously means that one
    product = named or (products[0] if len(products) == 1 else None)
    wants_advice = any(w in text for w in ("buy", "should", "worth", "wait", "deal", "good time", "cheap"))

    if product and any(w in text for w in ("check", "refresh", "update")):
        result = tools.check_price_now(product["id"])
        return result.get("error") or f"🔄 Checking the latest price of {product['name']}…"

    if named or (product and wants_advice):
        return format_advice(tools.get_buy_advice(product["id"]))

    if wants_advice and products:
        names = ", ".join(p["name"] for p in products[:5])
        return f"Which product do you mean? You're tracking: {names}."

    return "Hi! " + HELP_TEXT


# ------------------------------------------------------------- entry point
def clean_history(history: list) -> list:
    turns = [
        {"role": t["role"], "content": str(t["content"])[:2000]}
        for t in history
        if t.get("role") in ("user", "assistant") and t.get("content")
    ]
    return turns[-MAX_HISTORY:]


def chat(db, message: str, history: list, user_id: str = "demo-user") -> dict:
    tools = ChatTools(db, user_id)

    if llm_configured():
        try:
            reply = chat_with_llm(tools, message, clean_history(history))
            return {"reply": reply, "actions": tools.actions, "mode": "ai"}
        except Exception as exc:  # no internet, bad key, rate limit...
            print(f"WARNING: LLM call failed, using offline assistant: {exc}")
            if tools.actions:
                # A tool already changed something; don't repeat it in offline mode
                return {
                    "reply": "Done! (The AI service stopped responding, so I can't say more right now.)",
                    "actions": tools.actions,
                    "mode": "offline",
                }

    return {"reply": offline_reply(tools, message), "actions": tools.actions, "mode": "offline"}
