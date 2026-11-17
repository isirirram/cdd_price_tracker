import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

# Load worker environment variables
env_path = Path(__file__).with_name(".env")
load_dotenv(env_path)

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("MONGO_URI is missing!")

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)

db = client.get_default_database(default="price_tracker")

products_collection = db["products"]
price_history_collection = db["price_history"]

client.admin.command("ping")

print("MongoDB connected successfully!")
print("Database:", db.name)