"""Make the worker importable in tests without a real MongoDB or Redis.

worker/database.py connects to MongoDB at import time, so we swap in mongomock
before anything imports it.
"""
import os
import sys
from pathlib import Path

import mongomock
import pymongo

WORKER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKER_DIR))
sys.path.insert(0, str(WORKER_DIR.parent))  # so `import scraper` works

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/price_tracker_test")
pymongo.MongoClient = mongomock.MongoClient
