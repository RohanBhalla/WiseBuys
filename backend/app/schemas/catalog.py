from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class VendorProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=128)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    price_hint: Decimal | None = None
    differentiator: str | None = Field(default=None, max_length=4000)
    key_features: list[str] | None = None
    is_published: bool = False


class VendorProductCreate(VendorProductBase):
    pass


class VendorProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sku: str | None = None
    category: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    price_hint: Decimal | None = None
    differentiator: str | None = None
    key_features: list[str] | None = None
    is_published: bool | None = None


class VendorProductPublic(VendorProductBase):
    id: int
    vendor_user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
