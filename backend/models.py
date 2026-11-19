from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, model_validator


class ProductCreate(BaseModel):
    product_url: HttpUrl
    target_price: float = Field(gt=0)
    product_name: Optional[str] = None
    user_id: str = "demo-user"
    # Where the price-drop email goes. Optional: falls back to ALERT_EMAIL_TO.
    notify_email: Optional[EmailStr] = None
    # Telegram chat that gets the alert. Optional: falls back to TELEGRAM_CHAT_ID.
    # A numeric chat id (groups are negative) or a public @channelname.
    telegram_chat_id: Optional[str] = Field(
        default=None, pattern=r"^(-?\d{3,20}|@[A-Za-z0-9_]{5,32})$"
    )


class ProductOut(BaseModel):
    id: str
    user_id: str
    product_name: str
    product_url: str
    site: str
    target_price: float
    current_price: Optional[float] = None
    alert_sent: bool = False
    notify_email: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    image_url: Optional[str] = None
    # Set when this product is "the same product on another store"
    group_id: Optional[str] = None
    platform: Optional[str] = None
    created_at: datetime
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None


class CompareLinkCreate(BaseModel):
    """Another store's page for the same product (Shopify or WooCommerce)."""
    product_url: HttpUrl


class NotifyEmailUpdate(BaseModel):
    notify_email: Optional[EmailStr] = None


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

class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)
    user_id: str = "demo-user"
