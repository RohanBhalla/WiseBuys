from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.database import Base

_EMBEDDING_DIM = 768

if TYPE_CHECKING:
    from app.models.tag import ValueTag
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VendorProduct(Base):
    __tablename__ = "vendor_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    price_hint: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    differentiator: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_features: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)
    embedding_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    vendor: Mapped["User"] = relationship("User", back_populates="vendor_products")
    tag_links: Mapped[list["VendorProductTag"]] = relationship(
        "VendorProductTag",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class VendorProductTag(Base):
    """Vendor-asserted value tag attached to a specific product.

    The tag MUST be a subset of the parent vendor's `VendorAllowedTag` set
    (enforced at the API layer). Unique per (product, tag).
    """

    __tablename__ = "vendor_product_tags"
    __table_args__ = (UniqueConstraint("product_id", "tag_id", name="uq_vendor_product_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("vendor_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("value_tags.id", ondelete="CASCADE"), nullable=False, index=True
    )

    product: Mapped[VendorProduct] = relationship("VendorProduct", back_populates="tag_links")
    tag: Mapped["ValueTag"] = relationship("ValueTag", lazy="joined")
