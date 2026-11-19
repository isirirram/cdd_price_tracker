# Smart Price Tracker with Alerts

Track product prices, get an **email and/or Telegram message when a price drops to your
target**, compare the same product across Shopify and WooCommerce stores, and see
"best time to buy" insights, sale-event drop analysis and a budget planner.

| Part | Tech | Folder |
|---|---|---|
| Frontend | React + Vite (served by nginx) | `frontend/` |
| API | FastAPI + MongoDB | `backend/` |
| Price checker | Celery worker + Celery Beat + Redis | `worker/` |
| Price sources | Scraper adapters: demo store, Shopify, WooCommerce, BigCommerce, Wix, PrestaShop, OpenCart, Open Prices, any store with product data in its page | `scraper/` |
| Alerts | Email (SMTP) + Telegram bot | `worker/notifications.py` |
| AI assistant | LLM with tool calling (Groq / any OpenAI-compatible API) + offline fallback | `backend/chatbot.py` |
| CI/CD | GitHub Actions: tests, lint, build, Docker build, then push to GHCR | `.github/workflows/ci.yml` |

## Run everything

```bash
cp .env.example .env      # fill in SMTP_* and/or TELEGRAM_* to get real alerts
docker compose up --build
```

- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

Requires Docker Compose v2.24 or newer (Docker Desktop 4.27+). Only ports 3000 and 8000 need to
be free: MongoDB and Redis are reachable only from inside the Docker network. Every service
restarts automatically if it crashes, and the frontend waits until the API reports healthy.

Useful commands: `docker compose ps` (status), `docker compose logs -f worker` (watch price
checks and alerts), `docker compose down` (stop; data is kept in the `mongo_data` volume).

## Live demo of a price-drop alert

1. In the frontend, add `http://127.0.0.1:8001/products/product-001` with target price `1200`
   and your email (and/or Telegram chat id). Within a few seconds it shows the demo store
   price (₹1,499) and the product picture.
2. Drop the price on the demo store (it lives inside the worker container):
   ```bash
   docker compose exec worker python demo_price.py product-001 999
   ```
3. Click **Check Now** (or wait a few seconds) - the price becomes ₹999, the card shows
   "Target reached · alert sent ✓", and the email / Telegram message arrives.
4. Raise the price above the target and drop it again to get a new alert: one alert per
   price crossing, never duplicates.

Optional: `docker compose exec backend python seed_demo.py` adds 3 demo-store products with
45 days of history so the insights, drop report and budget pages have data to show.

## Alerts: email and Telegram

Alerts are sent on every channel that is set up. A product can have its own email and
Telegram chat id; otherwise `ALERT_EMAIL_TO` / `TELEGRAM_CHAT_ID` from `.env` are used.

- **Email:** set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`. For Gmail, turn on 2-Step
  Verification and use an App Password.
- **Telegram:** message [@BotFather](https://t.me/BotFather) → `/newbot` → put the token in
  `TELEGRAM_BOT_TOKEN`. Send any message to your bot, open
  `https://api.telegram.org/bot<TOKEN>/getUpdates`, and copy `"chat":{"id": ...}` into
  `TELEGRAM_CHAT_ID` (or into the "Telegram chat ID" field when adding a product).

**No duplicate alerts:** before sending, the worker *claims* the alert with one atomic
MongoDB update (`alert_sent: false → true`). If two checks of the same product run at the
same time (scheduled check + "Check Now"), only one wins the claim and sends. If every
channel fails, the claim is released so the next check retries. When the price goes back
above the target the alert re-arms.

**Alerts within minutes:** Celery Beat re-checks every product every
`CHECK_INTERVAL_SECONDS` (default 300 = 5 minutes, minimum 30; use 60 for a live demo).

## Compare prices across stores (Shopify + WooCommerce)

Open a product in **Price History** → **Compare Prices Across Stores** and paste the same
product's page on another Shopify (`https://store.com/products/<name>`) or WooCommerce
(`https://store.com/product/<name>`) store. Each store is tracked like a normal product
(price, history, alerts), and the table shows every store's price, cheapest first, with
how much you save.

API: `GET /products/{id}/compare`, `POST /products/{id}/compare {"product_url": "..."}`.

## Respecting the stores (robots.txt, rate limits, terms of service)

- Every request to a store first checks that store's **robots.txt** (RFC 9309, including
  `*` and `$` wildcards). Disallowed pages are never fetched and the product shows
  "robots.txt on <site> does not allow automated access to this page". If robots.txt
  can't be read (server error / unreachable) nothing is fetched.
- `Crawl-delay` is honoured, and every store gets at least 2 seconds between our requests.
- We identify ourselves honestly as `SmartPriceTracker/1.0` instead of pretending to be a
  browser.
- **Amazon, Flipkart and Croma are not supported.** Amazon and Flipkart only allow price
  access through partner APIs we don't have, and Croma's terms forbid automated price
  monitoring. Adding one of their links is rejected with an explanation.
- Store APIs and public product data are preferred over HTML pages (Shopify
  `/products/<handle>.js`, WooCommerce Store API, Schema.org product data).

## AI price assistant (💬 button, bottom-right)

- **"Should I buy the headphones now?"** - explains the buy-now / wait insight, past sale drops and your target
- **"What fits my budget?"** - best deals that fit in what's left of your monthly budget
- **"Track http://127.0.0.1:8001/products/product-002 under 2000, email me@example.com"** - adds the product

Set `LLM_API_KEY` in `.env` (free Groq key) for the AI mode: the LLM calls our own
backend functions (tools) for every number, so it can't make up prices. Without a key,
or if the internet is down, it automatically switches to the built-in offline assistant.

## How a price check flows

```
Frontend --POST /products--> FastAPI --saves--> MongoDB
                               |
                               +--"tasks.check_price"--> Redis --> Celery worker
                                                                     | robots.txt check -> scraper adapter -> price
                                                                     | save price + history to MongoDB
                                                                     | price <= target? -> claim alert -> email + Telegram
Celery Beat --every CHECK_INTERVAL_SECONDS--> "tasks.enqueue_all_products"
```

## CI/CD

One workflow, `.github/workflows/ci.yml`:

1. **CI** (every push and pull request to `main`): backend, scraper and worker tests;
   frontend lint and build; `docker compose config` and `docker compose build`.
2. **CD** (pushes to `main` only, and only after all CI jobs pass): builds and pushes the
   backend, frontend and worker images to GHCR, tagged `latest` and with the commit SHA.

## Running the tests locally

```bash
pip install -r backend/requirements.txt -r scraper/requirements.txt -r worker/requirements.txt mongomock
python -m pytest backend/tests
python -m pytest scraper/tests
python -m pytest worker/tests
cd frontend && npm ci && npm run lint && npm run build
```

## Running without Docker

Start MongoDB and Redis, copy `.env.example` to `.env` and set
`MONGO_URI=mongodb://localhost:27017/price_tracker` and `REDIS_URL=redis://localhost:6379/0`, then:

```bash
python scraper/demo_store/server.py --port 8001                                   # demo store
cd backend && uvicorn main:app --port 8000                                        # API
cd worker && celery -A celery_app.celery_app worker --loglevel=info               # worker
cd worker && celery -A celery_app.celery_app beat --loglevel=info                 # scheduler
cd frontend && npm run dev                                                        # http://localhost:5173
```

## Module documentation

- [`backend/README.md`](backend/README.md) - API endpoints, data model, analytics features
- [`scraper/README.md`](scraper/README.md) - adapters, data-retention policies, security

## Future work

- **User accounts.** The app currently runs as a single user and opens straight on the
  dashboard (every product belongs to `demo-user`). Next step: sign up / login with hashed
  passwords and tokens, so each user only sees their own products, budget and alerts.
- Price prediction with machine learning (out of scope in the problem statement).
