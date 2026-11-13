import os
from datetime import datetime, timezone
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

# Reads a .env file if one exists (backend/.env or repo-root .env).
# In Docker the variables come from docker-compose instead.
load_dotenv()

# Used only if the URI doesn't contain a database name.
DEFAULT_DB_NAME = "price_tracker"

NUMBER = ["double", "int", "long", "decimal"]

PRODUCTS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "user_id",
            "product_name",
            "product_url",
            "site",
            "target_price",
            "created_at",
        ],
        "properties": {
            "user_id": {"bsonType": "string"},
            "product_name": {"bsonType": "string"},
            "product_url": {"bsonType": "string"},
            "site": {"bsonType": "string"},
            "target_price": {"bsonType": NUMBER},
            "current_price": {"bsonType": NUMBER + ["null"]},
            "alert_sent": {"bsonType": "bool"},
            "created_at": {"bsonType": "date"},
        },
    }
}

PRICE_HISTORY_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["product_id", "price", "checked_at"],
        "properties": {
            "product_id": {"bsonType": "objectId"},
            "price": {"bsonType": NUMBER},
            "checked_at": {"bsonType": "date"},
        },
    }
}

BUDGETS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "monthly_budget"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "monthly_budget": {"bsonType": NUMBER},
            "spent_this_month": {"bsonType": NUMBER},
            "updated_at": {"bsonType": "date"},
        },
    }
}

SALE_EVENTS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "start_date", "end_date"],
        "properties": {
            "name": {"bsonType": "string"},
            "start_date": {"bsonType": "date"},
            "end_date": {"bsonType": "date"},
        },
    }
}


def _day(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


# APPROXIMATE placeholder dates. Check them against the real platform
# announcements and fix them (POST /sale-events or edit this list).
DEFAULT_SALE_EVENTS = [
    ("Diwali festive sales (approx.)", _day(2026, 10, 15), _day(2026, 11, 8)),
    ("Black Friday / Cyber Monday (approx.)", _day(2026, 11, 25), _day(2026, 11, 30)),
    ("Year-end sale (approx.)", _day(2026, 12, 20), _day(2026, 12, 31)),
    ("Republic Day sale (approx.)", _day(2027, 1, 15), _day(2027, 1, 26)),
]


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError(
            "MONGO_URI is not set. Create backend/.env with "
            "MONGO_URI=mongodb://localhost:27017/price_tracker"
        )
    return MongoClient(uri, serverSelectionTimeoutMS=5000)


def get_db() -> Database:
    # Uses the database named in the URI, or DEFAULT_DB_NAME if there is none.
    return get_client().get_default_database(default=DEFAULT_DB_NAME)


def _ensure_collection(db: Database, name: str, validator: dict) -> None:
    if name in db.list_collection_names():
        db.command("collMod", name, validator=validator)
    else:
        db.create_collection(name, validator=validator)


def seed_sale_events(db: Database) -> None:
    """Insert the default sale events only if the collection is empty."""
    if db.sale_events.count_documents({}) == 0:
        db.sale_events.insert_many(
            [
                {"name": name, "start_date": start, "end_date": end}
                for name, start, end in DEFAULT_SALE_EVENTS
            ]
        )


def init_db(db: Database) -> None:
    """Create all collections (with schema validation), indexes and seed data.
    Safe to run on every startup."""
    _ensure_collection(db, "products", PRODUCTS_VALIDATOR)
    _ensure_collection(db, "price_history", PRICE_HISTORY_VALIDATOR)
    _ensure_collection(db, "budgets", BUDGETS_VALIDATOR)
    _ensure_collection(db, "sale_events", SALE_EVENTS_VALIDATOR)

    db.products.create_index([("created_at", DESCENDING)])
    db.products.create_index([("user_id", ASCENDING)])
    db.price_history.create_index(
        [("product_id", ASCENDING), ("checked_at", ASCENDING)]
    )
    db.budgets.create_index([("user_id", ASCENDING)], unique=True)
    db.sale_events.create_index([("start_date", ASCENDING)])

    seed_sale_events(db)