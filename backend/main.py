import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure

from analytics import (
    build_budget_plan,
    build_drop_report,
    build_insights,
    to_naive_utc,
)
from database import get_db, init_db
from models import (
    BudgetSet,
    PricePoint,
    ProductCreate,
    ProductOut,
    SaleEventCreate,
    SaleEventOut,
)


def init_db_with_retry(attempts: int = 5, delay: int = 3) -> None:
    # In docker-compose the backend can start before MongoDB is ready,
    # so retry a few times before giving up.
    for attempt in range(1, attempts + 1):
        try:
            init_db(get_db())
            print("MongoDB ready: collections and indexes ensured.")
            return
        except ConnectionFailure:
            print(f"MongoDB not reachable (attempt {attempt}/{attempts}), retrying...")
            time.sleep(delay)
        except Exception as exc:  # e.g. MONGO_URI not set
            print(f"MongoDB setup failed: {exc}")
            return
    print("WARNING: MongoDB still unreachable. Requests will return 503 until it is up.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_with_retry()
    yield


app = FastAPI(title="Smart Price Tracker API", lifespan=lifespan)

# Lets the React frontend (Vite = 5173, CRA = 3000) call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    # Return 400 (as per the work division doc) instead of FastAPI's default 422
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid input", "errors": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(ConnectionFailure)
async def database_down_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid id")


def detect_site(url: str) -> str:
    host = urlparse(url).hostname or ""
    if "amazon" in host:
        return "amazon"
    if "flipkart" in host:
        return "flipkart"
    return "other"


def day_to_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def serialize(doc: dict) -> ProductOut:
    return ProductOut(
        id=str(doc["_id"]),
        user_id=doc.get("user_id", "demo-user"),
        product_name=doc.get("product_name", "Unknown product"),
        product_url=doc["product_url"],
        site=doc.get("site", "other"),
        target_price=doc["target_price"],
        current_price=doc.get("current_price"),
        alert_sent=doc.get("alert_sent", False),
        created_at=doc["created_at"],
    )


def serialize_event(doc: dict) -> SaleEventOut:
    return SaleEventOut(
        id=str(doc["_id"]),
        name=doc["name"],
        start_date=to_naive_utc(doc["start_date"]).date(),
        end_date=to_naive_utc(doc["end_date"]).date(),
    )


def get_product_or_404(db, product_id: str) -> dict:
    doc = db.products.find_one({"_id": to_object_id(product_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return doc


# ---------------------------------------------------------------- health
@app.get("/health")
def health(db=Depends(get_db)):
    db.command("ping")  # raises ConnectionFailure -> 503 if MongoDB is down
    return {"status": "ok", "database": "connected"}


# ------------------------------------------------- core product endpoints
@app.post("/products", response_model=ProductOut, status_code=201)
def add_product(payload: ProductCreate, db=Depends(get_db)):
    url = str(payload.product_url)
    doc = {
        "user_id": payload.user_id,
        "product_name": payload.product_name or "Pending first price check",
        "product_url": url,
        "site": detect_site(url),
        "target_price": payload.target_price,
        "current_price": None,
        "alert_sent": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = db.products.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@app.get("/products", response_model=list[ProductOut])
def list_products(db=Depends(get_db)):
    docs = db.products.find().sort("created_at", -1)
    return [serialize(d) for d in docs]


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db=Depends(get_db)):
    return serialize(get_product_or_404(db, product_id))


@app.get("/products/{product_id}/history", response_model=list[PricePoint])
def get_history(product_id: str, db=Depends(get_db)):
    product = get_product_or_404(db, product_id)
    rows = db.price_history.find({"product_id": product["_id"]}).sort("checked_at", 1)
    return [PricePoint(price=r["price"], checked_at=r["checked_at"]) for r in rows]


@app.delete("/products/{product_id}")
def delete_product(product_id: str, db=Depends(get_db)):
    oid = to_object_id(product_id)
    result = db.products.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    db.price_history.delete_many({"product_id": oid})  # clean up its history too
    return {"message": "Product removed from tracking"}


# ------------------------------- feature 2: best time to buy (insights)
@app.get("/products/{product_id}/insights")
def get_insights(product_id: str, db=Depends(get_db)):
    product = get_product_or_404(db, product_id)
    history = list(db.price_history.find({"product_id": product["_id"]}))
    events = list(db.sale_events.find())
    return {
        "product_id": product_id,
        "product_name": product.get("product_name"),
        **build_insights(history, events),
    }


# --------------------------------- feature 6: sale-event / drop tracker
@app.get("/products/{product_id}/drops")
def get_drops(product_id: str, db=Depends(get_db)):
    product = get_product_or_404(db, product_id)
    history = list(db.price_history.find({"product_id": product["_id"]}))
    events = list(db.sale_events.find())
    return {
        "product_id": product_id,
        "product_name": product.get("product_name"),
        **build_drop_report(history, events),
    }


@app.get("/sale-events", response_model=list[SaleEventOut])
def list_sale_events(db=Depends(get_db)):
    return [serialize_event(e) for e in db.sale_events.find().sort("start_date", 1)]


@app.post("/sale-events", response_model=SaleEventOut, status_code=201)
def add_sale_event(payload: SaleEventCreate, db=Depends(get_db)):
    doc = {
        "name": payload.name,
        "start_date": day_to_datetime(payload.start_date),
        "end_date": day_to_datetime(payload.end_date),
    }
    result = db.sale_events.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_event(doc)


@app.delete("/sale-events/{event_id}")
def delete_sale_event(event_id: str, db=Depends(get_db)):
    result = db.sale_events.delete_one({"_id": to_object_id(event_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Sale event not found")
    return {"message": "Sale event removed"}


# ---------------------------------------- feature 7: budget-based tracking
@app.put("/budget")
def set_budget(payload: BudgetSet, db=Depends(get_db)):
    db.budgets.update_one(
        {"user_id": payload.user_id},
        {
            "$set": {
                "monthly_budget": payload.monthly_budget,
                "spent_this_month": payload.spent_this_month,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    return {
        "user_id": payload.user_id,
        "monthly_budget": payload.monthly_budget,
        "spent_this_month": payload.spent_this_month,
    }


@app.get("/budget")
def get_budget_plan(user_id: str = "demo-user", db=Depends(get_db)):
    budget = db.budgets.find_one({"user_id": user_id})
    if not budget:
        raise HTTPException(
            status_code=404, detail="No budget set. Use PUT /budget first."
        )

    products = list(db.products.find({"user_id": user_id}))
    ids = [p["_id"] for p in products]
    averages = {
        row["_id"]: row["avg"]
        for row in db.price_history.aggregate(
            [
                {"$match": {"product_id": {"$in": ids}}},
                {"$group": {"_id": "$product_id", "avg": {"$avg": "$price"}}},
            ]
        )
    }
    plan = build_budget_plan(
        budget["monthly_budget"],
        budget.get("spent_this_month", 0.0),
        products,
        averages,
    )
    return {"user_id": user_id, **plan}