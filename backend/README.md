# Smart Price Tracker: Backend & API (Person 1)

FastAPI + MongoDB service that every other part of the project talks to.
It stores tracked products and their price history, and exposes the API used
by the frontend, the worker and the scraper integration.

**Stack:** Python, FastAPI, Uvicorn, PyMongo, Pydantic, Pytest (+ mongomock for tests)

**Status:** all 5 contract endpoints are done and tested. Three extra features
are also in: best-time-to-buy insights, sale-event tracking and budget planning.
`POST /products/{id}/check` is planned and will be added once the scraper works.

---

## 1. Quick start

```bash
git clone https://github.com/isirirram/cdd_price_tracker.git
cd cdd_price_tracker
git checkout feature/backend-api        # until it is merged into main
cd backend

python3 -m venv venv
source venv/bin/activate                # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` (it is git-ignored, never commit it):

```text
MONGO_URI=mongodb://localhost:27017/price_tracker
```

Start MongoDB (pick one):

```bash
# A) Docker
docker run -d --name mongo -p 27017:27017 mongo:7

# B) Homebrew (Mac, no Docker)
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

Run the API and open the interactive docs:

```bash
python -m uvicorn main:app --reload
# http://localhost:8000/docs
```

Run the tests (they use a fake in-memory database, so MongoDB is not needed):

```bash
python -m pytest -v          # expect 23 passed
```

Load demo data (3 products with 45 days of fake price history and a budget):

```bash
python seed_demo.py
```

> Always use `python -m pytest` and `python -m uvicorn`, not bare `pytest` /
> `uvicorn`. This guarantees they run inside the virtual environment.

---

## 2. Project structure

```text
backend/
├── main.py            FastAPI app and all endpoints
├── models.py          Pydantic request/response models (validation)
├── database.py        MongoDB connection, collection schemas, indexes
├── analytics.py       Logic for insights, sale-event drops, budget plan
├── seed_demo.py       Demo data loader
├── requirements.txt
├── Dockerfile
├── pytest.ini
└── tests/
    ├── test_products.py    core endpoints (12 tests)
    └── test_features.py    extra features (11 tests)
```

---

## 3. Environment variables

Names are shared by every service (see `.env.example` in the repo root).

| Variable | Used by | Example |
|---|---|---|
| `MONGO_URI` | backend, worker | `mongodb://localhost:27017/price_tracker` |
| `REDIS_URL` | worker | `redis://localhost:6379` |
| `TELEGRAM_BOT_TOKEN` | worker | (from BotFather) |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | worker | (email alerts, stretch goal) |

**Important: the database name is part of `MONGO_URI`** (`.../price_tracker`).
Everyone must use the same URI so all services read and write the same
database. Inside docker-compose the host changes to the service name:

```text
MONGO_URI=mongodb://mongo:27017/price_tracker
```

---

## 4. Data model (MongoDB)

MongoDB enforces these schemas. A write with the wrong types is rejected with
`Document failed validation`.

### `products`: one document per tracked product

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `user_id` | string | `"demo-user"` for now (no login yet) |
| `product_name` | string | placeholder until the first price check fills it in |
| `product_url` | string | |
| `site` | string | `"amazon"`, `"flipkart"` or `"other"` (set from the URL) |
| `target_price` | number | must be > 0 |
| `current_price` | number or **null** | `null` until the first price check |
| `alert_sent` | bool | **added to the contract** for duplicate-alert prevention |
| `created_at` | datetime | UTC |

### `price_history`: one document per price check

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `product_id` | **ObjectId** | NOT a string, or history queries return nothing |
| `price` | number | plain number, no "₹" or commas |
| `checked_at` | **datetime** | UTC, NOT a string |

### `budgets`: one document per user

`user_id` (string, unique), `monthly_budget` (number), `spent_this_month`
(number), `updated_at` (datetime).

### `sale_events`: festival / sale windows

`name` (string), `start_date` (datetime), `end_date` (datetime). Both ends are
inclusive. The default events are seeded on first startup. **Their dates are
approximate placeholders; check them against the real platform announcements
and fix them** (see `DEFAULT_SALE_EVENTS` in `database.py`, or use
`POST /sale-events` and `DELETE /sale-events/{id}`).

Indexes are created automatically on startup (`price_history` on
`product_id` + `checked_at`, etc.).

---

## 5. API reference

Base URL locally: `http://localhost:8000`. Full interactive docs at `/docs`.

### Core endpoints (from the shared contract)

| Method | Endpoint | Purpose | Success |
|---|---|---|---|
| POST | `/products` | Add a product URL + target price | 201 |
| GET | `/products` | List all tracked products (newest first) | 200 |
| GET | `/products/{id}` | One product's details | 200 |
| GET | `/products/{id}/history` | Price history, oldest first (chart-ready) | 200 |
| DELETE | `/products/{id}` | Stop tracking (also deletes its history) | 200 |
| GET | `/health` | Checks the API and the database connection | 200 |

**POST /products** request:

```json
{
  "product_url": "https://www.amazon.in/dp/XXXX",
  "target_price": 45000,
  "product_name": "optional",
  "user_id": "optional, defaults to demo-user"
}
```

Response (same shape as each item in `GET /products`):

```json
{
  "id": "6af3f40b4d8dcbb518fcc6dc",
  "user_id": "demo-user",
  "product_name": "Pending first price check",
  "product_url": "https://www.amazon.in/dp/XXXX",
  "site": "amazon",
  "target_price": 45000.0,
  "current_price": null,
  "alert_sent": false,
  "created_at": "2026-11-11T09:30:00Z"
}
```

**GET /products/{id}/history** response:

```json
[
  { "price": 52000.0, "checked_at": "2026-11-10T00:00:00Z" },
  { "price": 49000.0, "checked_at": "2026-11-11T00:00:00Z" }
]
```

### Extra feature endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/products/{id}/insights` | **Best time to buy:** buy now / wait / neutral suggestion |
| GET | `/products/{id}/drops` | **Sale-event tracker:** each price drop labelled `sale_event` or `standalone` |
| GET | `/sale-events` | List sale/festival windows |
| POST | `/sale-events` | Add one: `{"name": "...", "start_date": "2026-12-01", "end_date": "2026-12-05"}` |
| DELETE | `/sale-events/{id}` | Remove one |
| PUT | `/budget` | **Budget tracking:** set `{"monthly_budget": 60000, "spent_this_month": 0}` |
| GET | `/budget` | Best deals that fit in the remaining budget |

**Insights** (`/products/{id}/insights`). Key fields: `recommendation`
(`buy_now`, `wait`, `neutral` or `not_enough_data`), `reason`, `confidence`
(`low`, `medium`, `high`), `data_points`, `current_price`, `lowest_price`,
`highest_price`, `average_price`, `moving_average_7`, `trend_percent_per_check`,
`active_sale_event`, `sale_note`, `best_time_to_buy` (only after 14+ checks).
It is a statistical heuristic on the collected history, not machine learning
and not a guarantee. It needs at least 5 price checks.

**Drops** (`/products/{id}/drops`). Returns `drops[]` (each with `from_price`,
`to_price`, `drop_percent`, `detected_at`, `classification`, `sale_event`) and
a `summary` (counts and average drop % for sale vs standalone drops). Only
drops of 3% or more are listed.

**Budget** (`GET /budget`). Returns `recommended[]` (products below their
historical average, best deals first, that fit in the remaining budget),
`recommended_total`, `left_after_recommended`, `skipped[]` (with `reason`:
`over_budget` or `no_deal_yet`) and `waiting_for_first_price[]`. It does not
track purchases; `spent_this_month` is set manually.

### Error codes

| Code | Meaning |
|---|---|
| 400 | Bad input (empty URL, negative price, invalid id format, end date before start date) |
| 404 | Product / sale event / budget not found |
| 503 | MongoDB is unreachable |

### Planned

`POST /products/{id}/check`: calls the scraper, saves the price to
`price_history` and updates `current_price`. Will be added once Person 2's
`get_price` works.

---

## 6. For each teammate

### Person 2: Scraper

You do not need MongoDB or this API to start; build and test standalone.
Proposed contract (please confirm or change it):

```python
get_price(url) -> {"name": str, "price": float}
# On any failure (blocked, layout changed, dead link) raise ScraperError so the
# caller can log it and skip that product.
```

Return `price` as a plain float (no "₹" or commas). Suggested layout:
`scraper/__init__.py` (picks the parser by hostname), one file per site
(`amazon.py`, `flipkart.py`), and `test_scrape.py` (`python test_scrape.py <url>`).

### Person 3: Worker, Scheduler & Alerts

Read products and write prices directly in MongoDB using the same `MONGO_URI`.
The two types below matter: `product_id` must be an **ObjectId** and
`checked_at` a **datetime**.

```python
import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient

db = MongoClient(os.environ["MONGO_URI"]).get_default_database()

# after scraping a product:
db.price_history.insert_one({
    "product_id": ObjectId(product_id),
    "price": float(price),
    "checked_at": datetime.now(timezone.utc),
})
db.products.update_one(
    {"_id": ObjectId(product_id)},
    {"$set": {"current_price": float(price), "product_name": name}},
)

# duplicate-alert logic uses the alert_sent flag on the product:
#   price <= target_price and not alert_sent  -> send alert, set alert_sent True
#   price > target_price                      -> set alert_sent False (re-arm)
```

For the budget alert, call `GET /budget` after each round of checks and send
the `recommended` list on Telegram.

### Person 4: Frontend

- API base URL: keep it in `VITE_API_URL` (default `http://localhost:8000`).
- CORS is enabled for `http://localhost:5173` (Vite) and `http://localhost:3000`
  (Create React App). Tell Person 1 if you use another port.
- `current_price` is `null` until the first price check; show a "Waiting for
  first price" state instead of a number.
- `GET /products/{id}/history` is already sorted oldest first, ready for the
  chart.
- UI pieces for the extra features: a recommendation card (buy/wait, reason,
  confidence), a drop timeline with "Sale" / "Standalone" badges, and a budget
  page (recommended list and what is left).
- Use `python seed_demo.py` for realistic data while the worker is not ready.

### Person 5: DevOps, CI/CD & Docker

- The backend `Dockerfile` is in `backend/`. App entrypoint: `main:app`, port `8000`.
- Run the tests in CI from `backend/` with: `python -m pytest -v` (no database
  needed, 23 tests).
- Inside docker-compose use `MONGO_URI=mongodb://mongo:27017/price_tracker`.
  The backend retries the MongoDB connection for about 15 seconds on startup,
  so it tolerates starting before the database is ready.
- Health check endpoint: `GET /health` (returns 503 if MongoDB is down).
- Create `.env.example` in the repo root with every variable from section 3.

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `zsh: command not found: python` | On a Mac use `python3` to create the venv; once activated, `python` works |
| `ModuleNotFoundError: No module named 'dotenv'` (or another module) | `pip install -r requirements.txt` with the venv active |
| `No module named 'mongomock'` when running `pytest` | Use `python -m pytest`, not bare `pytest` |
| `MONGO_URI is not set` | Create `backend/.env` (see Quick start) |
| API returns 503 | MongoDB is not running or `MONGO_URI` is wrong |
| `Document failed validation` | A field has the wrong type (`product_id` must be an ObjectId, `checked_at` a datetime, prices numbers) |
| `docker build` fails with `no such host` | Network/DNS problem reaching Docker Hub; try another network or turn off the VPN |

---

## 8. Known limitations

- No login yet: everything uses `user_id = "demo-user"`.
- The budget feature does not track purchases.
- Sale-event dates are approximate defaults and must be checked.
- Insights improve as price history accumulates; with few checks they report
  `not_enough_data` or low confidence.
