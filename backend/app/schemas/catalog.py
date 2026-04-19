from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.tag import TagPublic


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
    tag_ids: list[int] = Field(
        default_factory=list,
        description="Subset of the vendor's allowed value tag ids to attach to this product.",
    )


class VendorProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sku: str | None = None
    category: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    price_hint: Decimal | None = None
    differentiator: str | None = None
    key_features: list[str] | None = None
    is_published: bool | None = None
    tag_ids: list[int] | None = Field(
        default=None,
        description="If provided, replaces the product's value tags with this subset of allowed tags.",
    )


class VendorProductPublic(VendorProductBase):
    id: int
    vendor_user_id: int
    tags: list[TagPublic] = []
    created_at: datetime
    updated_at: datetime

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
            "sku": data.sku,
            "category": data.category,
            "currency": data.currency,
            "price_hint": data.price_hint,
            "differentiator": data.differentiator,
            "key_features": data.key_features,
            "is_published": data.is_published,
            "tags": tags,
            "created_at": data.created_at,
            "updated_at": data.updated_at,
        }
