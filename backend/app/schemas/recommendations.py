from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, model_validator

from app.schemas.tag import TagPublic


class VendorProductSummary(BaseModel):
    id: int
    vendor_user_id: int
    name: str
    category: str | None = None
    currency: str | None = None
    price_hint: Decimal | None = None
    differentiator: str | None = None
    key_features: list[str] | None = None
    tags: list[TagPublic] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _flatten_tag_links(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        links = getattr(data, "tag_links", None)
        if links is None:
            return data
        tags = [link.tag for link in links if getattr(link, "tag", None)]
        return {
            "id": data.id,
            "vendor_user_id": data.vendor_user_id,
            "name": data.name,
            "category": data.category,
            "currency": data.currency,
            "price_hint": data.price_hint,
            "differentiator": data.differentiator,
            "key_features": data.key_features,
            "tags": tags,
        }


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
