from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ProductCreate(BaseModel):
    product_url: HttpUrl
    target_price: float = Field(gt=0)
    product_name: Optional[str] = None
    user_id: str = "demo-user"


class ProductOut(BaseModel):
    id: str
    user_id: str
    product_name: str
    product_url: str
    site: str
    target_price: float
    current_price: Optional[float] = None
    alert_sent: bool = False
    created_at: datetime


class PricePoint(BaseModel):
    price: float
    checked_at: datetime