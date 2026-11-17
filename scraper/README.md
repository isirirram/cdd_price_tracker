# Smart Price Tracker — Scraper & Price Extraction Module (Person 2)

**Component:** Person 2 — Scraper and Price Extraction  
**Project:** Smart Price Tracker with Automated Price Drop Alerts  
**Architecture:** Standardized Multi-Adapter Factory Pattern  
**Target Environment:** Windows (PowerShell) / Python 3.14  

---

## 1. Module Overview & Responsibilities

This module provides an isolated, standardized Python interface for retrieving product titles and current prices in Indian Rupees (`INR`). It operates completely independently of MongoDB, Redis, Celery, FastAPI, and React.

### Responsibilities of Person 2
* URL validation, cleaning, and domain routing.
* Extraction of platform-specific product identifiers (barcodes, slugs, ASINs, FSNs).
* Integration with authorized APIs and controlled demonstration endpoints.
* Currency normalization into numeric floats (`float` in `INR`).
* Strict enforcement of data retention and caching policies (`CachePolicy`).
* Standardized output modeling via Pydantic (`ScraperResult`).
* Domain error handling and safe logging without credential leakage.
* Standalone CLI test script and comprehensive automated Pytest test suite.
* Integration contract documentation for Person 3 (Worker/Scheduler).

---

## 2. Directory Structure

```text
scraper/
├── __init__.py               # Public API entry point: scrape_product(url)
├── base_scraper.py           # Abstract Base Class defining scraper contract
├── models.py                 # Pydantic models (ScraperResult, SourceCategory, CachePolicy)
├── exceptions.py             # Custom domain exception hierarchy
├── config.py                 # Environment configuration (.env reader)
├── scraper_factory.py        # Central URL router & adapter dispatcher
├── test_scraper.py           # Standalone CLI testing script
├── requirements.txt          # Pinned Python dependencies
├── README.md                 # This documentation
│
├── integrations/             # THE FIVE ADAPTER IMPLEMENTATIONS
│   ├── __init__.py
│   ├── open_prices.py        # Slot 1: Open-Data Price Observation (Open Food Facts)
│   ├── local_store.py        # Slot 2: Controlled Demonstration Storefront
│   ├── amazon.py             # Slot 3: Credential-Gated Amazon Creators API
│   ├── flipkart.py           # Slot 4: Credential-Gated Flipkart Affiliate API
│   └── croma.py              # Slot 5: Policy-Restricted Croma Adapter (Scrape Refusal)
│
├── demo_store/               # CONTROLLED DEMONSTRATION STOREFRONT SERVER
│   ├── __init__.py
│   └── server.py             # Self-contained HTTP server (127.0.0.1:8000)
│
└── tests/                    # AUTOMATED PYTEST SUITE
    ├── __init__.py
    ├── test_models.py        # Pydantic model validation tests
    ├── test_factory.py       # Domain detection and routing tests
    ├── test_open_prices.py   # Open Prices unit and mock tests
    ├── test_local_store.py   # LocalStore unit and live server tests
    ├── test_amazon.py        # Amazon Creators API contract tests (Mock fixtures)
    ├── test_flipkart.py      # Flipkart Affiliate API contract tests (Mock fixtures)
    ├── test_croma.py         # Policy restriction error handling tests
    │
    └── benchmark/            # QUARANTINED BENCHMARK / TEST FIXTURES ONLY
        ├── __init__.py
        ├── test_dummyjson.py # Resilience & pipeline error tests
        └── fixtures/         # Offline official JSON sample payloads
```

---

## 3. Environment Setup & Installation

### A. Activate Virtual Environment
Open Windows PowerShell in the project root (`cdd_price_tracker`):

```powershell
# Activate the isolated virtual environment
.\.venv\Scripts\Activate.ps1
```

### B. Dependencies
All dependencies are pinned in `scraper/requirements.txt`:
* `requests==2.34.2` — HTTP client with timeout management
* `python-dotenv==1.2.4` — Safe configuration loader
* `pytest==9.2.0` — Testing framework
* `pydantic==2.14.3` — Data modeling and validation

To install or verify:
```powershell
.\.venv\Scripts\python.exe -m pip install -r scraper/requirements.txt
```

---

## 4. The Five Data Source Adapters

| Slot | Adapter | Source Category | Identifier | Live Testable? | Historical Storage Permitted? | Cache TTL |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: |
| **1** | `OpenPricesAdapter` | `OPEN_DATA_OBSERVATION` | Barcode (8–14 digits) | **YES** | **YES** (ODbL 1.0) | Price: 24h, Meta: 7d |
| **2** | `LocalStoreAdapter` | `CONTROLLED_DEMO_STORE` | Product Slug/ID | **YES** | **YES** (Controlled) | Price: 60s, Meta: 24h |
| **3** | `AmazonCreatorsAdapter` | `CREDENTIAL_GATED` | ASIN (10 chars) | Gated | **NO** (Strictly forbidden) | Price: 1h, Meta: 24h |
| **4** | `FlipkartAffiliateAdapter` | `CREDENTIAL_GATED` | FSN / Product ID | Gated | **NO** (Contract gated) | Price: 24h, Meta: 24h |
| **5** | `CromaPolicyAdapter` | `POLICY_RESTRICTED` | Product Code | Refused | **N/A** (None) | None |

> **Important Limitation Disclosure:**  
> This project **does not claim support for five live commercial shopping websites**. Commercial Indian retail platforms (Amazon, Flipkart, Croma, etc.) legally prohibit automated web scraping under their Terms of Use and gate their APIs behind commercial sales volume or closed registration. We deliver two live working authorized data sources, two fully implemented credential-gated enterprise adapters, and one policy-enforcement adapter.

---

## 5. Running the Local Demonstration Storefront

Person 2 provides a self-contained local storefront server to enable live demonstrations of automated price tracking and real-time Telegram alerts.

### Start the Local Server
```powershell
.\.venv\Scripts\python.exe scraper/demo_store/server.py --port 8000
```

### Endpoints
* `GET http://127.0.0.1:8000/products/product-001` — Returns product JSON.
* `POST http://127.0.0.1:8000/admin/products/product-001/price` — Updates price dynamically.

**Live Price Drop Simulation Command:**
```powershell
# Lower price from ₹1,499 to ₹999
Invoke-RestMethod -Uri "http://127.0.0.1:8000/admin/products/product-001/price" -Method Post -Body '{"price": 999.0}' -ContentType "application/json"
```

---

## 6. Standalone CLI Testing Tool

You can test any adapter directly from the command line without running MongoDB or Celery:

```powershell
# Interactive mode
.\.venv\Scripts\python.exe scraper/test_scraper.py

# Direct argument mode: Open Prices barcode
.\.venv\Scripts\python.exe scraper/test_scraper.py "barcode:8901030825347"

# Direct argument mode: Local demonstration store
.\.venv\Scripts\python.exe scraper/test_scraper.py "http://127.0.0.1:8000/products/product-001"

# Direct argument mode: Amazon India (shows credential-gated status)
.\.venv\Scripts\python.exe scraper/test_scraper.py "https://www.amazon.in/dp/B08L5W4SW6"

# Direct argument mode: Croma (shows policy-restricted refusal)
.\.venv\Scripts\python.exe scraper/test_scraper.py "https://www.croma.com/sample/p/123456"
```

---

## 7. Running the Automated Test Suite

The test suite covers unit models, URL detection, mock responses, server security, and error boundaries:

```powershell
# Run the complete test suite
.\.venv\Scripts\pytest.exe scraper/tests -v
```

---

## 8. Integration Contract for Person 3 (Worker & Scheduler)

Person 3's Celery worker imports the top-level facade:

```python
from scraper import scrape_product

result = scrape_product(product_url)
```

### Return Contract (`ScraperResult`)
```python
result.success              # bool: True if extraction succeeded, False if failed
result.product_name         # Optional[str]: Clean title
result.current_price        # Optional[float]: Numeric price in INR (e.g. 1499.0)
result.currency             # str: "INR"
result.image_url            # Optional[str]: Validated HTTP/HTTPS URL of primary product image, or None
result.site                 # str: "open_prices", "local_store", "amazon", "flipkart", "croma"
result.source_category      # SourceCategory: OPEN_DATA_OBSERVATION, CONTROLLED_DEMO_STORE, etc.
result.is_commercial_store  # bool: False for Open Prices and LocalStore
result.checked_at           # datetime (UTC)
result.error                # Optional[str]: Descriptive error message if success is False
result.cache_policy         # Optional[CachePolicy]: Retention guidelines
result.attribution          # Optional[str]: Mandatory legal attribution
```

### Person 3 Implementation Rule for Cache & Price History
Person 3 **must** inspect `result.cache_policy.allow_historical_storage`:

```python
# In Person 3's Celery Task:
result = scrape_product(product_url)

if not result.success:
    logger.warning(f"Check failed for {product_url}: {result.error}")
    return

# 1. In-Memory Price Comparison (Always Permitted)
if result.current_price <= product.target_price:
    send_telegram_notification(
        user_id=product.user_id,
        product=result.product_name,
        price=result.current_price,
        image_url=result.image_url,
        attribution=result.attribution
    )

# 2. Strict Historical Storage Compliance Rule
if result.cache_policy and result.cache_policy.allow_historical_storage:
    # PERMITTED: Insert into price_history collection
    db.price_history.insert_one({
        "product_id": product.id,
        "price": result.current_price,
        "checked_at": result.checked_at
    })
else:
    # PROHIBITED: Do NOT insert into price_history (e.g. Amazon / Flipkart licenses)
    logger.info(f"Skipping price history insert for {result.site}: license forbids permanent retention.")

# 3. Product Collection Update with Cache Expiration TTL and Product Image
update_data = {
    "current_price": result.current_price,
    "last_checked_at": result.checked_at
}
if result.image_url:
    update_data["image_url"] = result.image_url
if result.cache_policy and result.cache_policy.price_ttl_seconds:
    update_data["price_expires_at"] = result.checked_at + timedelta(seconds=result.cache_policy.price_ttl_seconds)

db.products.update_one({"_id": product.id}, {"$set": update_data})
```

---

## 9. Legal and Licensing Disclaimers
* **Open Prices / Open Food Facts:** Data licensed under the Open Database License (ODbL v1.0). Applications displaying this data must credit Open Food Facts / Open Prices. The dataset is limited to groceries and packaged goods.
* **Amazon Creators API:** Subject to the Amazon Associates Operating Agreement. Prices may be cached for a maximum of 1 hour and must not be retained as a historical archive. Telegram alerts require user opt-in, mandatory timestamping, and pricing disclaimers.
* **Flipkart Affiliate API:** Subject to the Flipkart Affiliate Agreement. Direct developer sign-ups remain suspended.
* **Croma:** Terms of Use (Section 12) strictly prohibit automated scraping and data collection. Our adapter complies by refusing requests.

