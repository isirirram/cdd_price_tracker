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

# Automatic checks every 6 hours
celery_app.conf.beat_schedule = {
    "check-products-every-6-hours": {
        "task": "tasks.enqueue_all_products",
        "schedule": 21600.0,
    }
}

print("Celery configured successfully!")