"""
Self-contained Local Demonstration Storefront Server.

Runs exclusively on loopback (127.0.0.1) using Python's standard library http.server.
Provides product queries, image URLs, and dynamic price updates for project evaluation and live alerts.
"""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import re
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_store")

# In-memory product catalog (thread-safe for standard demo concurrency)
DEFAULT_CATALOG: Dict[str, Dict[str, Any]] = {
    "product-001": {
        "id": "product-001",
        "title": "Demo Wireless Noise-Cancelling Headphones",
        "price": 1499.0,
        "currency": "INR",
        "in_stock": True,
        "category": "Audio",
        "image_url": "http://127.0.0.1:8000/static/product-001.jpg"
    },
    "product-002": {
        "id": "product-002",
        "title": "Demo Smart Fitness Tracker Band",
        "price": 2499.0,
        "currency": "INR",
        "in_stock": True,
        "category": "Wearables",
        "image_url": "http://127.0.0.1:8000/static/product-002.jpg"
    },
    "product-003": {
        "id": "product-003",
        "title": "Demo RGB Mechanical Gaming Keyboard",
        "price": 3999.0,
        "currency": "INR",
        "in_stock": True,
        "category": "Peripherals",
        "image_url": "http://127.0.0.1:8000/static/product-003.jpg"
    },
    "product-004": {
        "id": "product-004",
        "title": "Demo Ergonomic Vertical Optical Mouse",
        "price": 899.0,
        "currency": "INR",
        "in_stock": True,
        "category": "Peripherals",
        "image_url": "http://127.0.0.1:8000/static/product-004.jpg"
    },
    "product-005": {
        "id": "product-005",
        "title": "Demo 4K Ultra-HD USB Webcam",
        "price": 4999.0,
        "currency": "INR",
        "in_stock": True,
        "category": "Cameras",
        "image_url": "http://127.0.0.1:8000/static/product-005.jpg"
    }
}

CATALOG: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in DEFAULT_CATALOG.items()}
ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class DemoStoreRequestHandler(BaseHTTPRequestHandler):
    """Handles GET /products/{id} and POST /admin/products/{id}/price requests."""

    def _send_json(self, status_code: int, data: Any):
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        """Handle product queries and health status."""
        path = self.path.split("?")[0].rstrip("/")

        # Root / Health check
        if path in ("", "/health", "/products"):
            self._send_json(200, {
                "status": "online",
                "service": "Smart Price Tracker Demonstration Storefront",
                "binding": "127.0.0.1",
                "available_products": list(CATALOG.keys())
            })
            return

        # GET /products/{id}
        match = re.match(r"^/products/([^/]+)$", path)
        if match:
            product_id = match.group(1)
            if not ID_REGEX.match(product_id):
                self._send_json(400, {
                    "error": "Invalid product ID format. Must match ^[a-zA-Z0-9_-]{1,64}$"
                })
                return

            if product_id in CATALOG:
                self._send_json(200, CATALOG[product_id])
            else:
                self._send_json(404, {
                    "error": f"Product with ID '{product_id}' not found in demonstration catalog.",
                    "available_ids": list(CATALOG.keys())
                })
            return

        self._send_json(404, {"error": "Endpoint not found."})

    def do_POST(self):
        """Handle administrative price updates."""
        path = self.path.split("?")[0].rstrip("/")

        # POST /admin/products/([^/]+)/price
        match = re.match(r"^/admin/products/([^/]+)/price$", path)
        if match:
            product_id = match.group(1)
            if not ID_REGEX.match(product_id):
                self._send_json(400, {"error": "Invalid product ID format."})
                return

            if product_id not in CATALOG:
                self._send_json(404, {"error": f"Product '{product_id}' not found."})
                return

            # Read and parse body
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                if content_len == 0 or content_len > 4096:
                    self._send_json(400, {"error": "Payload missing or exceeds 4KB limit."})
                    return

                raw_body = self.rfile.read(content_len).decode("utf-8")
                body = json.loads(raw_body)
            except Exception as e:
                self._send_json(400, {"error": f"Malformed JSON payload: {str(e)}"})
                return

            if not isinstance(body, dict) or "price" not in body:
                self._send_json(400, {"error": "Missing required field 'price'."})
                return

            try:
                new_price = float(body["price"])
            except (ValueError, TypeError):
                self._send_json(422, {"error": "Price must be a valid numeric float/int."})
                return

            # Validate price bounds
            if new_price < 0.01 or new_price > 10_000_000.0:
                self._send_json(422, {
                    "error": "Price must be strictly between ₹0.01 and ₹10,000,000.00."
                })
                return

            old_price = CATALOG[product_id]["price"]
            CATALOG[product_id]["price"] = round(new_price, 2)

            logger.info(f"Price updated for {product_id}: ₹{old_price} -> ₹{new_price}")

            self._send_json(200, {
                "success": True,
                "product_id": product_id,
                "title": CATALOG[product_id]["title"],
                "previous_price": old_price,
                "current_price": round(new_price, 2),
                "currency": "INR",
                "image_url": CATALOG[product_id].get("image_url"),
                "message": "Price updated successfully. Price tracker will detect change on next check."
            })
            return

        self._send_json(404, {"error": "Admin endpoint not found."})

    def log_message(self, format, *args):
        """Route internal server messages to standard logger."""
        logger.debug("%s - %s", self.address_string(), format % args)


def run_server(port: int = 8000, host: str = "127.0.0.1") -> HTTPServer:
    """Instantiate and start the HTTP server bound strictly to 127.0.0.1."""
    if host != "127.0.0.1":
        raise ValueError("Security violation: LocalStore server must bind exclusively to 127.0.0.1.")
    server_address = (host, port)
    httpd = HTTPServer(server_address, DemoStoreRequestHandler)
    logger.info(f"Local Demonstration Storefront running at http://{host}:{port}/")
    return httpd


def reset_catalog():
    """Reset catalog in-place to initial state (used for testing)."""
    CATALOG.clear()
    for k, v in DEFAULT_CATALOG.items():
        CATALOG[k] = dict(v)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local Demonstration Storefront Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    args = parser.parse_args()

    httpd = run_server(port=args.port, host="127.0.0.1")
    print(f"================================================================")
    print(f"SMART PRICE TRACKER - CONTROLLED DEMONSTRATION STOREFRONT")
    print(f"Binding Address: http://127.0.0.1:{args.port}/")
    print(f"Sample Product: http://127.0.0.1:{args.port}/products/product-001")
    print(f"Price Update:   POST http://127.0.0.1:{args.port}/admin/products/product-001/price")
    print(f"Press Ctrl+C to stop.")
    print(f"================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LocalStore server...")
        httpd.server_close()
