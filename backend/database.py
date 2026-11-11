import os

from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "price_tracker")

_client = MongoClient(MONGO_URI)


def get_db():
    return _client[DB_NAME]