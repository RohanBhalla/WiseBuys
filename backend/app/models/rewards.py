from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RewardEventType(str, enum.Enum):
    account_linked = "account_linked"
    aligned_purchase = "aligned_purchase"
    onboarding_complete = "onboarding_complete"
    redemption = "redemption"
    adjustment = "adjustment"


class RewardEvent(Base):
    """Append-only ledger entry. Positive `points` is an earn; negative is a
    redemption / clawback. Idempotency is enforced via `dedupe_key`."""

    __tablename__ = "reward_events"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_reward_event_dedupe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[RewardEventType] = mapped_column(
        Enum(RewardEventType, name="reward_event_type"), nullable=False, index=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    related_purchase_id: Mapped[int | None] = mapped_column(
        ForeignKey("knot_purchases.id", ondelete="SET NULL"), nullable=True
    )
    related_vendor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
