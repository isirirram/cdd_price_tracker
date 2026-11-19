import os
from pathlib import Path
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).with_name(".env")
load_dotenv(env_path)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)

celery_app = Celery(
    "price_tracker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)

celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)

# Automatic checks. Default every 5 minutes, so an alert goes out within a few
# minutes of a price drop. The scraper still obeys robots.txt / Crawl-delay and
# spaces out requests to each store. For a live demo, 60 is fine.
# Never below 30 s, so a typo can't make us hammer the stores.
CHECK_INTERVAL_SECONDS = max(30.0, float(os.getenv("CHECK_INTERVAL_SECONDS", "300")))

celery_app.conf.beat_schedule = {
    "check-all-products": {
        "task": "tasks.enqueue_all_products",
        "schedule": CHECK_INTERVAL_SECONDS,
    }
}

print("Celery configured successfully!")