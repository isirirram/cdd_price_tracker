"""Lets the API ask the Celery worker to check a price right away.

The backend doesn't import the worker code. It just puts a message called
"tasks.check_price" on the Redis queue, and the worker picks it up.

If REDIS_URL isn't set (e.g. running the API alone, or in tests) this does
nothing and returns False, so the API still works without the worker.
"""

import os
from functools import lru_cache

from celery import Celery


@lru_cache(maxsize=1)
def _client():
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    app = Celery("price_tracker_api", broker=url)
    app.conf.broker_connection_retry_on_startup = False
    app.conf.broker_transport_options = {"max_retries": 1}
    return app


def queue_price_check(product_id: str) -> bool:
    client = _client()
    if client is None:
        return False
    try:
        client.send_task("tasks.check_price", args=[product_id], retry=False)
        return True
    except Exception as exc:  # Redis down: don't fail the request
        print(f"WARNING: could not queue price check for {product_id}: {exc}")
        return False
