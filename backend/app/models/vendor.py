from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.tag import ValueTag
    from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VendorApplicationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    needs_info = "needs_info"
    approved = "approved"
    rejected = "rejected"


class VendorApplication(Base):
    __tablename__ = "vendor_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[VendorApplicationStatus] = mapped_column(
        Enum(VendorApplicationStatus, name="vendor_application_status"),
        default=VendorApplicationStatus.submitted,
        nullable=False,
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    applicant: Mapped["User"] = relationship(
        "User", back_populates="vendor_applications", foreign_keys=[applicant_user_id]
    )
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by_user_id])
    requested_tags: Mapped[list["VendorApplicationTag"]] = relationship(
        "VendorApplicationTag", back_populates="application", cascade="all, delete-orphan"
    )


class VendorApplicationTag(Base):
    __tablename__ = "vendor_application_tags"
    __table_args__ = (UniqueConstraint("application_id", "tag_id", name="uq_application_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("vendor_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("value_tags.id", ondelete="CASCADE"), nullable=False)

    application: Mapped[VendorApplication] = relationship("VendorApplication", back_populates="requested_tags")
    tag: Mapped["ValueTag"] = relationship("ValueTag")


class VendorProfile(Base):
    __tablename__ = "vendor_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendor_applications.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="vendor_profile")
    allowed_tags: Mapped[list["VendorAllowedTag"]] = relationship(
        "VendorAllowedTag", back_populates="vendor_profile", cascade="all, delete-orphan"
    )


class VendorAllowedTag(Base):
    """Tags an admin has approved this vendor to display."""

    __tablename__ = "vendor_allowed_tags"
    __table_args__ = (UniqueConstraint("vendor_profile_id", "tag_id", name="uq_vendor_allowed_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_profile_id: Mapped[int] = mapped_column(
        ForeignKey("vendor_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("value_tags.id", ondelete="CASCADE"), nullable=False)

    vendor_profile: Mapped[VendorProfile] = relationship("VendorProfile", back_populates="allowed_tags")
    tag: Mapped["ValueTag"] = relationship("ValueTag")
