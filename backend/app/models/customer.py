from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.tag import ValueTag
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    primary_focus_tag_id: Mapped[int | None] = mapped_column(
        ForeignKey("value_tags.id", ondelete="SET NULL"), nullable=True
    )
    rewards_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="customer_profile")
    primary_focus: Mapped["ValueTag | None"] = relationship("ValueTag", foreign_keys=[primary_focus_tag_id])
    secondary_focuses: Mapped[list["CustomerSecondaryFocus"]] = relationship(
        "CustomerSecondaryFocus", back_populates="profile", cascade="all, delete-orphan"
    )


class CustomerSecondaryFocus(Base):
    __tablename__ = "customer_secondary_focuses"
    __table_args__ = (UniqueConstraint("profile_id", "tag_id", name="uq_customer_secondary_focus"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("value_tags.id", ondelete="CASCADE"), nullable=False)

    profile: Mapped[CustomerProfile] = relationship("CustomerProfile", back_populates="secondary_focuses")
    tag: Mapped["ValueTag"] = relationship("ValueTag")
