from datetime import datetime, timezone
from urllib.parse import urlparse

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import get_db
from models import PricePoint, ProductCreate, ProductOut

app = FastAPI(title="Smart Price Tracker API")

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


def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid product id")


def detect_site(url: str) -> str:
    host = urlparse(url).hostname or ""
    if "amazon" in host:
        return "amazon"
    if "flipkart" in host:
        return "flipkart"
    return "other"


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


@app.get("/health")
def health():
    return {"status": "ok"}


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
    doc = db.products.find_one({"_id": to_object_id(product_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize(doc)


@app.get("/products/{product_id}/history", response_model=list[PricePoint])
def get_history(product_id: str, db=Depends(get_db)):
    oid = to_object_id(product_id)
    if not db.products.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Product not found")
    rows = db.price_history.find({"product_id": oid}).sort("checked_at", 1)
    return [PricePoint(price=r["price"], checked_at=r["checked_at"]) for r in rows]


@app.delete("/products/{product_id}")
def delete_product(product_id: str, db=Depends(get_db)):
    oid = to_object_id(product_id)
    result = db.products.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    db.price_history.delete_many({"product_id": oid})  # clean up its history too
    return {"message": "Product removed from tracking"}