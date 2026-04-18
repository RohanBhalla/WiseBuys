from datetime import datetime

from pydantic import BaseModel, Field

from app.models.rewards import RewardEventType


class RewardEventPublic(BaseModel):
    id: int
    event_type: RewardEventType
    points: int
    description: str | None = None
    related_purchase_id: int | None = None
    related_vendor_user_id: int | None = None
    extra: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RewardSummary(BaseModel):
    balance: int
    events: list[RewardEventPublic]


class AdminAdjustmentRequest(BaseModel):
    user_id: int
    points: int = Field(description="Positive to credit, negative to debit")
    description: str = Field(min_length=1, max_length=500)
    dedupe_key: str | None = None


class RecomputeRequest(BaseModel):
    user_id: int | None = None
