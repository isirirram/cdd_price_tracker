# Smart Price Tracker with Email Alerts

Track product prices, get an **email when a price drops to your target**, and see
"best time to buy" insights, sale-event drop analysis and a budget planner.

| Part | Tech | Folder |
|---|---|---|
| Frontend | React + Vite (served by nginx) | `frontend/` |
| API | FastAPI + MongoDB | `backend/` |
| Price checker | Celery worker + Celery Beat + Redis | `worker/` |
| Price sources | Scraper adapters (demo store, Open Prices, Amazon/Flipkart APIs) | `scraper/` |
| CI/CD | GitHub Actions (tests, lint, build, Docker build, push to GHCR) | `.github/workflows/` |

## Run everything

```bash
cp .env.example .env      # fill in SMTP_* to get real emails; CHECK_INTERVAL_SECONDS=60 for demos
docker compose up --build
```

- Frontend: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

## Live demo of a price-drop alert

1. In the frontend, add `http://127.0.0.1:8001/products/product-001` with target price `1200`
   and your email. Within a few seconds it shows the demo store price (₹1,499).
2. Drop the price on the demo store (it lives inside the worker container):
   ```bash
   docker compose exec worker python demo_price.py product-001 999
   ```
3. Click **Check Now** (or wait a few seconds) — the price becomes ₹999, the card shows
   "Target reached · alert sent ✓", and the email arrives.

Optional: `docker compose exec backend python seed_demo.py` adds 3 demo products with
45 days of history so the insights, drop report and budget pages have data to show.

## How a price check flows

```
Frontend --POST /products--> FastAPI --saves--> MongoDB
                               |
                               +--"tasks.check_price"--> Redis --> Celery worker
                                                                     | scraper adapter -> current price
                                                                     | save price + history to MongoDB
                                                                     | price <= target? -> send email
Celery Beat --every CHECK_INTERVAL_SECONDS--> "tasks.enqueue_all_products"
```

---

# Smart Price Tracker – Scraper & Price Extraction Module

## 1. Overview

The Scraper & Price Extraction module is responsible for identifying supported product sources, extracting product information and retrieving the latest available product prices.

It accepts a product URL or barcode, identifies the corresponding source, extracts the product name and current price, and returns the information in a standardized format for the backend and price-monitoring worker.

This module was developed as **Person 2's contribution** to the Smart Price Tracker with Automated Price Drop Alerts project.

## 2. Objectives

- Accept and validate product URLs and supported barcode inputs.
- Identify the product source automatically.
- Extract product names and current prices.
- Support multiple source adapters through a common architecture.
- Handle invalid URLs, unsupported websites, missing credentials and network errors.
- Follow source-specific caching and data-retention policies.
- Provide a standardized output for integration with Person 3's worker module.
- Support independent testing of the scraper without requiring the complete application.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| Requests | HTTP requests and API communication |
| Pydantic | Data validation and structured results |
| Python-dotenv | Environment variable management |
| Pytest | Automated testing |
| Git & GitHub | Version control and collaboration |

## 4. Project Structure

```text
cdd_price_tracker/
│
├── .env.example
├── .gitignore
│
└── scraper/
    ├── __init__.py
    ├── requirements.txt
    ├── models.py
    ├── exceptions.py
    ├── config.py
    ├── base_scraper.py
    ├── scraper_factory.py
    ├── test_scraper.py
    ├── README.md
    │
    ├── integrations/
    │   ├── __init__.py
    │   ├── open_prices.py
    │   ├── local_store.py
    │   ├── amazon.py
    │   ├── flipkart.py
    │   └── croma.py
    │
    ├── demo_store/
    │   ├── __init__.py
    │   └── server.py
    │
    └── tests/
        ├── __init__.py
        ├── test_models.py
        ├── test_factory.py
        ├── test_open_prices.py
        ├── test_local_store.py
        ├── test_amazon.py
        ├── test_flipkart.py
        ├── test_croma.py
        │
        └── benchmark/
            ├── __init__.py
            ├── test_dummyjson.py
            └── fixtures/
```

## 5. Module Architecture

The scraper follows an object-oriented, factory-based architecture.

### BaseScraper

Provides a common interface for all scraper adapters. It defines the methods required for URL validation, product identification and product extraction.

### ScraperFactory

Identifies the source from the supplied URL and selects the appropriate adapter. It also handles unsupported sources and errors.

### Models

The module uses Pydantic models to maintain a consistent structure for extracted product information.

**ScraperResult** contains:

- Success status
- Product name
- Current price
- Currency
- Website/source
- Product URL
- Source category
- Commercial-store indicator
- Timestamp
- Error information
- Cache policy
- Attribution information

**CachePolicy** defines source-specific price and metadata expiration periods and whether historical price storage is permitted.

### Exceptions

Custom exceptions are used to handle different failures, including:

- Invalid URL
- Unsupported website
- Missing API credentials
- Registration restrictions
- Policy-restricted websites
- Network timeout
- Product not found

## 6. Supported Integrations

The module implements five adapter categories.

### 1. Open Prices

- Uses the Open Prices and Open Food Facts ecosystem.
- Supports barcode-based product identification.
- Retrieves available price observations.
- Does not require API credentials.
- Focuses on groceries and packaged consumer products.
- Provides attribution and follows the applicable open-data licensing requirements.

### 2. LocalStore

- A controlled demonstration storefront developed for this project.
- Runs locally using Python's built-in HTTP server.
- Allows product information and prices to be retrieved.
- Supports simulated price changes.
- Used for end-to-end testing of the scraper.
- Does not represent a commercial shopping platform.

### 3. Amazon

- Uses the Amazon Creators API integration structure.
- Requires valid API credentials and an eligible Associates account.
- Implements credential checks and response parsing.
- Uses source-specific caching restrictions.
- Historical price storage is disabled in the adapter.

### 4. Flipkart

- Uses the Flipkart Affiliate API integration structure.
- Requires approved affiliate credentials.
- Handles credential validation and API response parsing.
- Historical price storage is disabled in the adapter.

### 5. Croma

- Implemented as a policy-restricted adapter.
- Does not perform automated scraping.
- Refuses unsupported extraction requests.
- Does not send network requests.

**Note:** Implementing five adapter categories does not mean five live commercial shopping websites are supported. Amazon and Flipkart require credentials, Open Prices is a price-observation data source, LocalStore is a demo storefront, and Croma refuses scraping.

## 7. Local Demonstration Storefront

A local storefront was created to test the complete scraper workflow independently.

It runs on:

```text
http://127.0.0.1:8000
```

Features include:

- Product catalogue with sample products.
- Product details and current prices.
- Availability information.
- Price update functionality.
- Local HTTP endpoints for product retrieval and price updates.

The server is restricted to the localhost address and uses in-memory data.

## 8. Installation and Setup

### Step 1: Create a virtual environment

```powershell
python -m venv .venv
```

### Step 2: Activate the environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

```powershell
pip install -r scraper/requirements.txt
```

### Step 4: Configure environment variables

Copy `.env.example` to `.env` and provide the required credentials for integrations that need them.

The LocalStore and Open Prices adapters do not require the Amazon or Flipkart credentials.

## 9. Running the Scraper

### Start the LocalStore server

Open a terminal in the project root and execute:

```powershell
.\.venv\Scripts\python.exe scraper/demo_store/server.py --port 8000
```

Keep the server running.

### Run the scraper

Open another terminal and execute:

```powershell
.\.venv\Scripts\python.exe scraper/test_scraper.py "http://127.0.0.1:8000/products/product-001"
```

The scraper retrieves the product name, current price and other relevant information.

### Simulate a price change

Use the following command in the second terminal:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/admin/products/product-001/price" -ContentType "application/json" -Body '{"price":999}'
```

This updates the demo product's price to ₹999.

Run the scraper again:

```powershell
.\.venv\Scripts\python.exe scraper/test_scraper.py "http://127.0.0.1:8000/products/product-001"
```

The scraper retrieves the updated price.

## 10. Automated Testing

Pytest was used to test the scraper module.

The test suite covers:

- Pydantic model validation.
- URL identification and factory routing.
- Open Prices barcode parsing.
- LocalStore product extraction and price updates.
- Amazon credential checks and API response parsing.
- Flipkart credential checks and API response parsing.
- Croma policy restrictions.
- Error handling and network timeout scenarios.
- DummyJSON benchmark isolation.

Run the complete test suite:

```powershell
.\.venv\Scripts\pytest.exe scraper/tests -v
```

### Test Results

| Metric | Result |
|---|---:|
| Total tests | 39 |
| Passed | 39 |
| Failed | 0 |
| Success rate | 100% |

The implementation report recorded all 39 tests as passing.

## 11. Integration with Person 3

The scraper provides a public function that allows the worker module to retrieve product information.

Example:

```python
from scraper import scrape_product

result = scrape_product(product_url)

if result.success:
    print(result.product_name)
    print(result.current_price)
else:
    print(result.error)
```

The returned result can be used by the worker to:

1. Retrieve the latest available product price.
2. Compare it with the user's target price.
3. Trigger the appropriate alert workflow.
4. Store price history only when the source's retention policy permits it.
5. Respect the source-specific cache expiration rules.

**Important:** Person 3 must enforce the returned cache and historical-storage policies before saving prices in the database.

## 12. Limitations

- Amazon requires eligible Associates API credentials for live access.
- Flipkart requires approved affiliate credentials.
- Open Prices is limited to products with available barcode-based observations.
- LocalStore is only a controlled demonstration environment.
- Croma does not support automated scraping through this adapter.
- Amazon and Flipkart integrations were tested using mock API responses rather than live credentials.
- The module does not independently schedule price checks or send notifications.

## 13. Scope of Contribution

The work completed under Person 2 includes:

- Scraper architecture and configuration.
- Product URL validation and source identification.
- Five source adapters.
- Product name and price extraction.
- Error handling and cache policies.
- Local demonstration storefront.
- Standalone scraper testing tool.
- Automated test suite.
- Documentation and integration interface for Person 3.

The module does not implement the backend database, scheduling system, notification services, frontend or DevOps pipeline, as these are assigned to other team members.

## 14. Conclusion

The Scraper & Price Extraction module provides a structured and reusable way to retrieve product information and current prices from supported sources.

It was independently tested using automated tests and a controlled local storefront. The successful demonstration included retrieving a product's original price, updating the price and retrieving the updated value through the scraper.

The module is prepared for integration with the worker and scheduler component of the Smart Price Tracker project.
