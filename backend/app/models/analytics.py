from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.catalog import VendorProduct
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecommendationClick(Base):
    """Customer click on a recommended vendor product.

    Lightweight engagement signal so vendors can see real interest beyond reach.
    """

    __tablename__ = "recommendation_clicks"
    __table_args__ = (
        Index("ix_rec_clicks_vendor_created", "vendor_user_id", "created_at"),
        Index("ix_rec_clicks_product_created", "product_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("vendor_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(64), default="dashboard", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    product: Mapped["VendorProduct"] = relationship("VendorProduct")
