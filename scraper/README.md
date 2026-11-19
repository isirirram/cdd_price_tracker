# Smart Price Tracker — Scraper & Price Extraction Module (Person 2)

**Component:** Person 2 — Scraper and Price Extraction  
**Project:** Smart Price Tracker with Automated Price Drop Alerts  
**Architecture:** Standardized Multi-Adapter Factory Pattern with SSRF Protection  
**Target Environment:** Windows (PowerShell) / Python 3.14  

---

## 1. Module Overview & Responsibilities

This module provides an isolated, standardized Python interface for retrieving product titles, current prices in Indian Rupees (`INR`) or store currencies, and primary product image URLs across **12 e-commerce platforms and data sources** (including arbitrary public shopping websites via structured metadata extraction). It operates completely independently of MongoDB, Redis, Celery, FastAPI, and React.

### Responsibilities of Person 2
* URL validation, cleaning, and domain routing across 12 platforms and generic web stores.
* Extraction of platform-specific product identifiers (barcodes, slugs, ASINs, FSNs, handles, URL IDs).
* Multi-method structured metadata extraction (Schema.org JSON-LD, Open Graph, Twitter cards, standard meta).
* Integration with authorized public storefront endpoints, official APIs, and controlled demo servers.
* SSRF (Server-Side Request Forgery) protection, private IP blocking, and safe redirect validation.
* Currency and price normalization into numeric floats (`float` in `INR`/major currency units).
* Minor currency unit conversions (Shopify cents/paise, WooCommerce minor units).
* Product image URL extraction and protocol normalization (`//` and relative paths to absolute HTTPS URLs).
* Strict enforcement of data retention and caching policies (`CachePolicy`).
* Standardized output modeling via Pydantic (`ScraperResult`).
* Standalone CLI test script and comprehensive automated Pytest test suite (108 passing tests).
* Integration contract documentation for Person 3 (Worker/Scheduler).

---

## 2. Directory Structure

```text
scraper/
├── __init__.py               # Public API entry point: scrape_product(url)
├── base_scraper.py           # Abstract Base Class defining scraper contract
├── models.py                 # Pydantic models (ScraperResult, SourceCategory, CachePolicy)
├── exceptions.py             # Custom domain exception hierarchy
├── security.py               # SSRF protection, private IP blocking, safe HTTP & JSON-LD
├── config.py                 # Environment configuration (.env reader)
├── scraper_factory.py        # Central URL router & adapter dispatcher
├── test_scraper.py           # Standalone CLI testing script
├── requirements.txt          # Pinned Python dependencies
├── README.md                 # This documentation
│
├── integrations/             # THE TWELVE ADAPTER IMPLEMENTATIONS
│   ├── __init__.py
│   ├── open_prices.py        # Slot 1: Open-Data Price Observation (Open Food Facts)
│   ├── local_store.py        # Slot 2: Controlled Demonstration Storefront
│   ├── croma.py              # Slot 5: Policy-Restricted Croma Adapter (Scrape Refusal)
│   ├── shopify.py            # Slot 6: Shopify Storefront Ajax API (/products/{handle}.js)
│   ├── woocommerce.py        # Slot 7: WooCommerce Public Store API (/wp-json/wc/store/v1)
│   ├── bigcommerce.py        # Slot 8: BigCommerce Storefront Structured Data
│   ├── wix.py                # Slot 9: Wix eCommerce Storefront JSON-LD
│   ├── prestashop.py         # Slot 10: PrestaShop Storefront JSON-LD
│   ├── opencart.py           # Slot 11: OpenCart Storefront Structured Data
│   └── generic.py            # Slot 12: Generic Structured Metadata Scraper (JSON-LD / OG)
│
├── demo_store/               # CONTROLLED DEMONSTRATION STOREFRONT SERVER
│   ├── __init__.py
│   └── server.py             # Self-contained HTTP server (127.0.0.1:8001)
│
└── tests/                    # AUTOMATED PYTEST SUITE (108 TESTS)
    ├── __init__.py
    ├── test_models.py        # Pydantic model validation & SourceCategory tests
    ├── test_factory.py       # Domain detection and routing tests (all 12 adapters)
    ├── test_security.py      # SSRF validation, private IP blocking, redirect safety
    ├── test_open_prices.py   # Open Prices unit and mock tests
    ├── test_local_store.py   # LocalStore unit and price-drop simulation tests
    ├── test_croma.py         # Policy restriction error handling tests
    ├── test_shopify.py       # Shopify Ajax API unit, variant & minor-unit tests
    ├── test_woocommerce.py   # WooCommerce Store API & minor-unit conversion tests
    ├── test_bigcommerce.py   # BigCommerce structured data & auth gate tests
    ├── test_additional_platforms.py # Wix, PrestaShop, OpenCart mock & auth tests
    ├── test_generic.py       # Slot 12: JSON-LD, @graph, OG, meta, and anti-bot tests
    │
    └── benchmark/            # QUARANTINED BENCHMARK / TEST FIXTURES ONLY
        ├── __init__.py
        ├── test_dummyjson.py # Resilience & pipeline error tests
        └── fixtures/         # Offline JSON/HTML sample payloads
```

---

## 3. Environment Setup & Installation

### A. Virtual Environment
Run Windows PowerShell from the project root (`cdd_price_tracker`):

```powershell
# Activate the isolated virtual environment
.\.venv\Scripts\Activate.ps1
```

### B. Dependencies
All dependencies are pinned in `scraper/requirements.txt`:
* `requests==2.34.2` — HTTP client with timeout management
* `python-dotenv==1.2.4` — Safe configuration loader
* `pytest==9.2.0` — Automated testing framework
* `pydantic==2.14.3` — Data modeling and validation

*No extra external dependencies are required.* Platform parsing uses standard library `re`, `json`, `socket`, `ipaddress`, and `urllib.parse`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r scraper/requirements.txt
```

---

## 4. The Eleven Supported Platform Adapters

| Slot | Adapter | Source Category | Identifier | Endpoint / Mechanism | Historical Storage Permitted? | Cache TTL |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: |
| **1** | `OpenPricesAdapter` | `OPEN_DATA_OBSERVATION` | Barcode (8–14 digits) | Open Food Facts API | **YES** (ODbL 1.0) | Price: 24h, Meta: 7d |
| **2** | `LocalStoreAdapter` | `CONTROLLED_DEMO_STORE` | Product Slug/ID | Demo Server `127.0.0.1:8001` | **YES** (Controlled) | Price: 60s, Meta: 24h |
| **5** | `CromaPolicyAdapter` | `POLICY_RESTRICTED` | Product Code | Refusal (Zero network calls) | **N/A** (None) | None |
| **6** | `ShopifyAdapter` | `PUBLIC_STORE_API` | Product Handle | `/products/{handle}.js` | **YES** (Public API) | Price: 1h, Meta: 24h |
| **7** | `WooCommerceAdapter` | `PUBLIC_STORE_API` | Slug / Numeric ID | `/wp-json/wc/store/v1/products` | **YES** (Public API) | Price: 1h, Meta: 24h |
| **8** | `BigCommerceAdapter` | `PUBLIC_STORE_API` | Product Slug | Storefront Schema.org JSON-LD | **YES** (Public storefront) | Price: 1h, Meta: 24h |
| **9** | `WixAdapter` | `PUBLIC_STORE_API` | Product Slug | Storefront Schema.org JSON-LD | **YES** (Public storefront) | Price: 1h, Meta: 24h |
| **10** | `PrestaShopAdapter` | `PUBLIC_STORE_API` | ID / Slug | Storefront Schema.org JSON-LD | **YES** (Public storefront) | Price: 1h, Meta: 24h |
| **11** | `OpenCartAdapter` | `PUBLIC_STORE_API` | Product ID / Slug | Storefront JSON-LD & OpenGraph | **YES** (Public storefront) | Price: 1h, Meta: 24h |

---

## 5. Platform-Specific Integration Details

### Priority 1: Main Platform Integrations

#### 1. Shopify (`scraper/integrations/shopify.py`)
- **How it works:** Queries the official public Ajax API endpoint: `https://{domain}/products/{product-handle}.js`.
- **Price Conversion:** Shopify Ajax API returns prices in **minor currency units** (e.g. `2499900` minor units represents ₹24,999.00 or $24,999.00). The adapter divides by 100 to yield clean major currency floats.
- **Variants:** If `?variant=12345` is present in the product URL, the adapter searches the `variants` array and retrieves that specific variant's price and image.
- **Images:** Extracts `featured_image` or variant image. Automatically converts protocol-relative image URLs (`//cdn.shopify.com/...` to `https://cdn.shopify.com/...`).
- **Example URLs:**
  - `https://store.myshopify.com/products/the-all-mountain-snowboard`
  - `https://shop.gymshark.com/products/crest-hoodie`
  - `shopify://store.myshopify.com/products/snowboard?variant=804171196`
- **Limitations:** Password-protected stores, private B2B wholesale portals, or deleted items return structured error results (`HTTP 401/403/404`).

#### 2. WooCommerce (`scraper/integrations/woocommerce.py`)
- **How it works:** Uses the official public **WooCommerce Store API** (`/wp-json/wc/store/v1/products?slug={slug}` or `/wp-json/wc/store/v1/products/{id}`).
- **Price Conversion:** The Store API provides `prices.price` with `prices.currency_minor_unit` (e.g., `"249900"` with `currency_minor_unit: 2` converts to ₹2,499.00).
- **Images:** Extracts the primary image URL from `images[0].src`.
- **Example URLs:**
  - `https://example.com/product/flying-ninja/` (Default WooCommerce singular `/product/` permalink)
  - `https://store.com/?product=99`
  - `woocommerce://store.com/product/hoodie`
- **Limitations:** If a site operator disables the Store API or installs restrictive security plugins that block `/wp-json/`, the adapter returns a clean, structured refusal without crashing.

#### 3. BigCommerce (`scraper/integrations/bigcommerce.py`)
- **How it works:** Fetches the public storefront product page using safe HTTP requests and parses standard **Schema.org JSON-LD** structured data (`<script type="application/ld+json">`) and Stencil meta tags.
- **Authentication Handling:** If a store is private, password-gated, or requires private API credentials (`X-Auth-Token`), the adapter detects HTTP 401/403 and returns an authentication-required error. Never fabricates fake prices.
- **Example URLs:**
  - `https://store.mybigcommerce.com/products/sample-item.html`
  - `https://store.mybigcommerce.com/pro-running-shoes/`
  - `bigcommerce://store.com/products/sample`

---

### Priority 2: Additional Platform Integrations

#### 4. Wix eCommerce (`scraper/integrations/wix.py`)
- **How it works:** Parses public storefront Schema.org JSON-LD microdata from `/product-page/{slug}`.
- **Example URL:** `https://store.wixsite.com/boutique/product-page/leather-handbag`
- **Limitations:** Stores requiring client-side login or private membership return structured authentication-required errors.

#### 5. PrestaShop (`scraper/integrations/prestashop.py`)
- **How it works:** Parses public storefront Schema.org JSON-LD microdata from rewrite paths (`/{id}-{slug}.html` or `?id_product=`).
- **Example URL:** `https://store.com/12-printed-summer-dress.html`
- **Limitations:** PrestaShop Web Service API (`/api/`) requires an API key (HTTP 401). When private, returns an authentication-required error.

#### 6. OpenCart (`scraper/integrations/opencart.py`)
- **How it works:** Parses public storefront Schema.org JSON-LD and OpenGraph microdata from standard parameter paths (`route=product/product&product_id=42`).
- **Example URL:** `https://store.com/index.php?route=product/product&product_id=42`
- **Limitations:** Stores in maintenance mode or requiring customer login return structured access-restricted errors.

---

### Priority 3: Universal Structured Metadata Scraper (Arbitrary E-commerce Stores)

#### 7. Generic E-commerce Scraper (`scraper/integrations/generic.py`)
- **How it works:** Serves as the fallback adapter in `ScraperFactory` for any publicly accessible shopping website not recognized as a dedicated platform (e.g. YETI, REI, Nordstrom, Patagonia, specialized D2C brands).
- **Multi-Method Extraction Priority:**
  1. **Method 1 — Schema.org JSON-LD:** Searches HTML for `<script type="application/ld+json">`. Handles `Product`, `ProductGroup`, `IndividualProduct`, `ProductModel`, nested `@graph` arrays, and `hasVariant` structures. Prioritizes in-stock offers and selects the lowest valid price.
  2. **Method 2 — Open Graph Metadata:** Parses `og:title`, `og:image`, `product:price:amount`, `og:price:amount`, and `og:price:currency`.
  3. **Method 3 — Standard & Twitter Metadata:** Parses `twitter:title`, `twitter:image`, and `<meta name="price">`, with clean fallback from `<title>`.
- **Image URL Resolution:** Safely converts relative (`/img.jpg`) and protocol-relative (`//cdn.site.com/img.jpg`) URLs into absolute HTTPS URLs using `urljoin`.
- **Anti-Bot & Access Gate Handling:** If a site (e.g., YETI via Akamai/Cloudflare) blocks automated script requests with HTTP 403 or requires CAPTCHAs/passwords, the adapter returns a clean, descriptive error (`Access to '<domain>' is restricted or blocked by anti-bot protections`) without crashing. Never fabricates fake prices.
- **Example URLs:**
  - `https://www.yeti.com/drinkware/tumblers/21071509045.html`
  - `https://shop.nordstrom.com/s/item-name/12345`
  - `https://store.outdoorbrand.com/items/camping-tent`
- **Cache Policy:**
  - Price TTL: 3,600 seconds (1 hour)
  - Metadata TTL: 86,400 seconds (24 hours)
  - Historical Storage: `True` (public web storefront data)

---

## 6. Security & SSRF Protection Architecture (`scraper/security.py`)

All web-facing adapters route requests through `scraper/security.py` to prevent Server-Side Request Forgery (SSRF) and data leakage:

1. **Protocol Whitelisting:** Strictly permits `http://` and `https://`. Rejects `file://`, `ftp://`, `gopher://`, `javascript:`, etc.
2. **Localhost & Loopback Blocking:** Blocks `localhost`, `127.0.0.1`, `::1`, and `0.0.0.0`.
3. **Private Network Address Filtering:** Resolves hostnames via DNS and rejects any destination resolving to private IPv4/IPv6 ranges:
   - `10.0.0.0/8` (RFC 1918)
   - `172.16.0.0/12` (RFC 1918)
   - `192.168.0.0/16` (RFC 1918)
   - `169.254.0.0/16` (Link-local cloud metadata)
   - `fe80::/10` (IPv6 Link-local)
   - `fc00::/7` (IPv6 Unique Local)
4. **Internal Domain Suffix Rejection:** Blocks `.local`, `.internal`, `.lan`, `.localhost`, and `.home.arpa`.
5. **Safe Redirect Validation:** Inspects every HTTP redirect (301, 302, 307, 308) and validates that the target URL does not redirect into a private network.
6. **Request Timeouts:** Mandatory 10-second timeout on all network calls.
7. *Controlled Exception:* The `LocalStoreAdapter` explicitly targets `127.0.0.1:8001` solely for controlled local development and simulation.

---

## 7. Running the Local Demonstration Storefront

Person 2 provides a self-contained local storefront server to enable live demonstrations of automated price tracking and real-time email / Telegram alerts.

### Start the Local Server
```powershell
.\.venv\Scripts\python.exe scraper/demo_store/server.py --port 8001
```

### Endpoints
* `GET http://127.0.0.1:8001/products/product-001` — Returns product JSON.
* `POST http://127.0.0.1:8001/admin/products/product-001/price` — Updates price dynamically.

**Live Price Drop Simulation Command:**
```powershell
# Lower price from ₹1,499 to ₹999
Invoke-RestMethod -Uri "http://127.0.0.1:8001/admin/products/product-001/price" -Method Post -Body '{"price": 999.0}' -ContentType "application/json"
```

---

## 8. Standalone CLI Testing Tool

You can test any adapter directly from the command line without running MongoDB or Celery:

```powershell
# Interactive mode
.\.venv\Scripts\python.exe scraper/test_scraper.py

# Direct argument mode: Shopify
.\.venv\Scripts\python.exe scraper/test_scraper.py "https://store.myshopify.com/products/snowboard"

# Direct argument mode: WooCommerce
.\.venv\Scripts\python.exe scraper/test_scraper.py "https://example.com/product/flying-ninja"

# Direct argument mode: BigCommerce
.\.venv\Scripts\python.exe scraper/test_scraper.py "https://store.mybigcommerce.com/products/sample-item"

# Direct argument mode: Open Prices barcode
.\.venv\Scripts\python.exe scraper/test_scraper.py "barcode:8901030825347"

# Direct argument mode: Local demonstration store
.\.venv\Scripts\python.exe scraper/test_scraper.py "http://127.0.0.1:8001/products/product-001"

# Direct argument mode: Croma (shows policy-restricted refusal)
.\.venv\Scripts\python.exe scraper/test_scraper.py "https://www.croma.com/sample/p/123456"

# Direct argument mode: Generic E-commerce Store (YETI)
.\.venv\Scripts\python.exe scraper/test_scraper.py "https://www.yeti.com/drinkware/tumblers/21071509045.html"
```

---

## 9. Running the Automated Test Suite

The test suite covers unit models, URL detection, SSRF protection, mock responses, server security, and error boundaries across all 12 adapters:

```powershell
# Run the complete test suite (108 passing tests)
.\.venv\Scripts\pytest.exe scraper/tests -v
```

---

## 10. Integration Contract for Person 3 (Worker & Scheduler)

Person 3's Celery worker imports the top-level facade:

```python
from scraper import scrape_product

result = scrape_product(product_url)
```

### Return Contract (`ScraperResult`)
```python
result.success              # bool: True if extraction succeeded, False if failed
result.product_name         # Optional[str]: Clean title
result.current_price        # Optional[float]: Numeric price in INR / store currency (e.g. 1499.0)
result.currency             # str: "INR", "USD", etc.
result.image_url            # Optional[str]: Validated HTTP/HTTPS URL of primary product image, or None
result.site                 # str: "shopify", "woocommerce", "bigcommerce", "open_prices", "local_store", etc.
result.source_category      # SourceCategory: PUBLIC_STORE_API, OPEN_DATA_OBSERVATION, CONTROLLED_DEMO_STORE, etc.
result.is_commercial_store  # bool: True for commercial stores (Shopify, WooCommerce, BigCommerce, etc.)
result.checked_at           # datetime (UTC)
result.error                # Optional[str]: Descriptive error message if success is False
result.cache_policy         # Optional[CachePolicy]: Retention guidelines
result.attribution          # Optional[str]: Mandatory legal attribution
```

### Person 3 Implementation Rule for Cache, Price History & Alerts

```python
# In Person 3's Celery Task:
result = scrape_product(product_url)

if not result.success:
    logger.warning(f"Check failed for {product_url}: {result.error}")
    return

# 1. Price Comparison & Telegram Alert with Image Preview
if result.current_price <= product.target_price:
    send_telegram_notification(
        user_id=product.user_id,
        product=result.product_name,
        price=result.current_price,
        currency=result.currency,
        image_url=result.image_url,    # Passed directly to Telegram bot (e.g. send_photo)
        attribution=result.attribution
    )

# 2. Strict Historical Storage Compliance Rule
if result.cache_policy and result.cache_policy.allow_historical_storage:
    # PERMITTED: Insert into price_history collection (Shopify, WooCommerce, BigCommerce, Open Prices, LocalStore)
    db.price_history.insert_one({
        "product_id": product.id,
        "price": result.current_price,
        "currency": result.currency,
        "checked_at": result.checked_at
    })
else:
    # PROHIBITED: Do NOT insert into price_history (sources whose licence forbids it)
    logger.info(f"Skipping price history insert for {result.site}: license forbids permanent retention.")

# 3. Product Collection Update with Cache Expiration TTL and Product Image
update_data = {
    "current_price": result.current_price,
    "currency": result.currency,
    "last_checked_at": result.checked_at
}
if result.image_url:
    update_data["image_url"] = result.image_url

if result.cache_policy and result.cache_policy.price_ttl_seconds:
    update_data["price_expires_at"] = result.checked_at + timedelta(seconds=result.cache_policy.price_ttl_seconds)

db.products.update_one({"_id": product.id}, {"$set": update_data})
```

---

## 11. Legal and Licensing Disclaimers
* **Shopify Stores:** Sourced via standard public storefront Ajax endpoints (`/products/{handle}.js`). Only public, unauthenticated catalog data is retrieved.
* **WooCommerce Stores:** Sourced via the public WooCommerce Store API (`/wp-json/wc/store/v1/`). Stores restricting the API return structured error results.
* **BigCommerce, Wix, PrestaShop, OpenCart:** Sourced via publicly accessible storefront structured data (Schema.org JSON-LD microdata). Private/B2B/password-protected stores return authentication-required errors.
* **Open Prices / Open Food Facts:** Data licensed under the Open Database License (ODbL v1.0). Applications displaying this data must credit Open Food Facts / Open Prices.
* **Croma:** Terms of Use (Section 12) strictly prohibit automated scraping. Adapter complies by refusing requests.
* **Amazon / Flipkart:** Not supported. They only allow price access through partner APIs (Amazon Creators API, Flipkart Affiliate API) that need approved accounts, and their terms forbid scraping. The adapters were removed and their URLs are rejected.
* **robots.txt:** Every storefront request goes through `security.safe_get`, which checks the site's robots.txt first (`scraper/robots.py`, RFC 9309 with wildcards), honours `Crawl-delay`, and spaces requests to the same site by at least 2 seconds.
