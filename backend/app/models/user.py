from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.catalog import VendorProduct
    from app.models.customer import CustomerProfile
    from app.models.vendor import VendorApplication, VendorProfile


class UserRole(str, enum.Enum):
    customer = "customer"
    vendor = "vendor"
    admin = "admin"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    customer_profile: Mapped["CustomerProfile | None"] = relationship(
        "CustomerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    vendor_profile: Mapped["VendorProfile | None"] = relationship(
        "VendorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    vendor_applications: Mapped[list["VendorApplication"]] = relationship(
        "VendorApplication",
        back_populates="applicant",
        foreign_keys="VendorApplication.applicant_user_id",
        cascade="all, delete-orphan",
    )
    vendor_products: Mapped[list["VendorProduct"]] = relationship(
        "VendorProduct", back_populates="vendor", cascade="all, delete-orphan"
    )
