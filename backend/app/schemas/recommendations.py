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


class RecommendationItem(BaseModel):
    product: VendorProductSummary
    score: float
    reasons: list[str]
    evidence_line_item_ids: list[int]


class SpendingInsight(BaseModel):
    knot_merchant_id: int
    merchant_name: str | None = None
    currency: str | None = None
    purchase_count: int
    total_spent: float
