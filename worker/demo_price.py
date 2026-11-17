"""Change a price on the built-in demo store and immediately re-check all products.

The demo store only listens on 127.0.0.1 *inside the worker container*, so it
can't be reached from your laptop. Run this inside the container instead:

    docker compose exec worker python demo_price.py product-001 999

Then refresh the frontend: the new price (and an email alert, if 999 is below
the target) should appear within a few seconds.
"""

import argparse
import os

import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("product_id", help="demo product id, e.g. product-001")
    parser.add_argument("price", type=float, help="new price in INR")
    parser.add_argument(
        "--no-check", action="store_true", help="only change the price, don't trigger a check"
    )
    args = parser.parse_args()

    base = os.getenv("LOCAL_STORE_URL", "http://127.0.0.1:8001").rstrip("/")
    resp = requests.post(
        f"{base}/admin/products/{args.product_id}/price",
        json={"price": args.price},
        timeout=5,
    )
    print(resp.json())
    resp.raise_for_status()

    if not args.no_check:
        from tasks import enqueue_all_products

        enqueue_all_products.delay()
        print("Queued a price check for all tracked products.")


if __name__ == "__main__":
    main()
