from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


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


class SaleEventCreate(BaseModel):
    name: str = Field(min_length=1)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class SaleEventOut(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date


class BudgetSet(BaseModel):
    monthly_budget: float = Field(gt=0)
    spent_this_month: float = Field(default=0, ge=0)
    user_id: str = "demo-user"