from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class VendorProductSummary(BaseModel):
    id: int
    vendor_user_id: int
    name: str
    category: str | None = None
    currency: str | None = None
    price_hint: Decimal | None = None
    differentiator: str | None = None
    key_features: list[str] | None = None

    model_config = {"from_attributes": True}


class ComparablePurchase(BaseModel):
    line_item_id: int | None = None
    name: str
    merchant_name: str | None = None
    unit_price: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None
    occurred_at: datetime | None = None


class RecommendationItem(BaseModel):
    product: VendorProductSummary
    score: float
    reasons: list[str]
    insight: str = ""
    comparable: ComparablePurchase | None = None
    evidence_line_item_ids: list[int]


class RecommendationClickCreate(BaseModel):
    product_id: int
    source: str | None = None


class RecommendationClickPublic(BaseModel):
    id: int
    product_id: int
    vendor_user_id: int
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SpendingInsight(BaseModel):
    knot_merchant_id: int
    merchant_name: str | None = None
    currency: str | None = None
    purchase_count: int
    total_spent: float
