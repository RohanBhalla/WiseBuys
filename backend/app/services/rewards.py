from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CustomerProfile,
    KnotPurchase,
    RewardEvent,
    RewardEventType,
    User,
    VendorAllowedTag,
    VendorProfile,
)

ACCOUNT_LINKED_POINTS = 100
ONBOARDING_COMPLETE_POINTS = 50
ALIGNED_PURCHASE_CAP = 250  # max points granted per purchase


@dataclass
class GrantResult:
    granted: bool
    event: RewardEvent | None
    reason: str | None = None


def _record_event(
    db: Session,
    *,
    user_id: int,
    event_type: RewardEventType,
    points: int,
    dedupe_key: str,
    description: str | None = None,
    related_purchase_id: int | None = None,
    related_vendor_user_id: int | None = None,
    extra: dict | None = None,
) -> GrantResult:
    """Insert a ledger row idempotently. Duplicate dedupe_keys are silently
    skipped so callers can be invoked from webhooks safely."""

    event = RewardEvent(
        user_id=user_id,
        event_type=event_type,
        points=points,
        dedupe_key=dedupe_key,
        description=description,
        related_purchase_id=related_purchase_id,
        related_vendor_user_id=related_vendor_user_id,
        extra=extra,
    )
    # Duplicate dedupe_key must not call session.rollback() — that would undo other
    # flushed work in the same transaction (e.g. Knot purchases during sync).
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        return GrantResult(granted=False, event=None, reason="duplicate")
    return GrantResult(granted=True, event=event)


def grant_account_linked(
    db: Session, *, user: User, knot_merchant_id: int, merchant_name: str | None
) -> GrantResult:
    return _record_event(
        db,
        user_id=user.id,
        event_type=RewardEventType.account_linked,
        points=ACCOUNT_LINKED_POINTS,
        dedupe_key=f"account_linked:{knot_merchant_id}",
        description=f"Linked {merchant_name or f'merchant #{knot_merchant_id}'}",
        extra={"knot_merchant_id": knot_merchant_id, "merchant_name": merchant_name},
    )


def grant_onboarding_complete_if_eligible(db: Session, *, user: User) -> GrantResult:
    profile = (
        db.query(CustomerProfile)
        .options(selectinload(CustomerProfile.secondary_focuses))
        .filter(CustomerProfile.user_id == user.id)
        .one_or_none()
    )
    if profile is None:
        return GrantResult(granted=False, event=None, reason="no_profile")
    if profile.primary_focus_tag_id is None or not profile.secondary_focuses:
        return GrantResult(granted=False, event=None, reason="incomplete")
    return _record_event(
        db,
        user_id=user.id,
        event_type=RewardEventType.onboarding_complete,
        points=ONBOARDING_COMPLETE_POINTS,
        dedupe_key="onboarding_complete",
        description="Completed values onboarding",
    )


def _focus_tag_ids(profile: CustomerProfile) -> set[int]:
    ids: set[int] = set()
    if profile.primary_focus_tag_id:
        ids.add(profile.primary_focus_tag_id)
    ids.update(link.tag_id for link in profile.secondary_focuses if link.tag_id)
    return ids


def _matching_vendor_for_purchase(
    db: Session,
    *,
    purchase: KnotPurchase,
    user_focus_tag_ids: set[int],
) -> VendorProfile | None:
    """Find the first approved vendor whose company name matches the merchant
    name AND whose allowed tags overlap the customer's focuses."""

    if not purchase.merchant_name or not user_focus_tag_ids:
        return None

    needle = f"%{purchase.merchant_name.strip().lower()}%"
    vendors = (
        db.query(VendorProfile)
        .options(selectinload(VendorProfile.allowed_tags))
        .filter(func.lower(VendorProfile.company_legal_name).like(needle))
        .all()
    )
    for vendor in vendors:
        allowed = {link.tag_id for link in vendor.allowed_tags if link.tag_id}
        if allowed & user_focus_tag_ids:
            return vendor
    return None


def grant_aligned_purchase_if_eligible(
    db: Session, *, user: User, purchase: KnotPurchase
) -> GrantResult:
    if purchase.total is None or float(purchase.total) <= 0:
        return GrantResult(granted=False, event=None, reason="no_total")
    if purchase.order_status and purchase.order_status.upper() in {
        "CANCELLED",
        "REFUNDED",
        "RETURNED",
        "FAILED",
    }:
        return GrantResult(granted=False, event=None, reason="non_completed")

    profile = (
        db.query(CustomerProfile)
        .options(selectinload(CustomerProfile.secondary_focuses))
        .filter(CustomerProfile.user_id == user.id)
        .one_or_none()
    )
    if profile is None:
        return GrantResult(granted=False, event=None, reason="no_profile")

    focus_ids = _focus_tag_ids(profile)
    vendor = _matching_vendor_for_purchase(db, purchase=purchase, user_focus_tag_ids=focus_ids)
    if vendor is None:
        return GrantResult(granted=False, event=None, reason="no_aligned_vendor")

    points = min(int(round(float(purchase.total))), ALIGNED_PURCHASE_CAP)
    if points <= 0:
        return GrantResult(granted=False, event=None, reason="zero_points")

    return _record_event(
        db,
        user_id=user.id,
        event_type=RewardEventType.aligned_purchase,
        points=points,
        dedupe_key=f"aligned_purchase:{purchase.knot_transaction_id}",
        description=(
            f"Aligned purchase at {purchase.merchant_name} "
            f"(matched vendor {vendor.company_legal_name})"
        ),
        related_purchase_id=purchase.id,
        related_vendor_user_id=vendor.user_id,
        extra={"order_total": str(purchase.total), "currency": purchase.currency},
    )


def grant_aligned_purchases_for_user(db: Session, user: User) -> dict:
    """Sweep recent purchases for a user and grant aligned-purchase rewards.
    Idempotent thanks to per-transaction dedupe keys."""

    purchases = (
        db.query(KnotPurchase)
        .filter(KnotPurchase.user_id == user.id)
        .order_by(KnotPurchase.occurred_at.desc().nullslast())
        .limit(200)
        .all()
    )
    granted = 0
    points = 0
    for p in purchases:
        result = grant_aligned_purchase_if_eligible(db, user=user, purchase=p)
        if result.granted and result.event is not None:
            granted += 1
            points += result.event.points
    return {"events_granted": granted, "points_awarded": points}


def get_balance(db: Session, user: User) -> int:
    total = (
        db.query(func.coalesce(func.sum(RewardEvent.points), 0))
        .filter(RewardEvent.user_id == user.id)
        .scalar()
    )
    return int(total or 0)


def list_events(
    db: Session, user: User, *, limit: int = 50, offset: int = 0
) -> list[RewardEvent]:
    return (
        db.query(RewardEvent)
        .filter(RewardEvent.user_id == user.id)
        .order_by(RewardEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def admin_adjust(
    db: Session,
    *,
    user: User,
    points: int,
    description: str,
    dedupe_key: str | None = None,
) -> GrantResult:
    return _record_event(
        db,
        user_id=user.id,
        event_type=RewardEventType.adjustment,
        points=points,
        dedupe_key=dedupe_key or f"adjustment:{user.id}:{description}",
        description=description,
    )


def grant_for_purchases(
    db: Session, *, user: User, purchases: Iterable[KnotPurchase]
) -> list[GrantResult]:
    """Used from the Knot sync path to grant points as new purchases land."""

    results: list[GrantResult] = []
    for p in purchases:
        results.append(grant_aligned_purchase_if_eligible(db, user=user, purchase=p))
    return results
