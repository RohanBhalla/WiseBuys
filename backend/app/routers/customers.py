import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_customer, get_db

logger = logging.getLogger(__name__)
from app.models import CustomerProfile, CustomerSecondaryFocus, User, ValueTag
from app.schemas.customer import CustomerProfilePublic, CustomerProfileUpdate
from app.services.rewards import grant_onboarding_complete_if_eligible

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _get_or_create_profile(db: Session, user: User) -> CustomerProfile:
    profile = db.query(CustomerProfile).filter(CustomerProfile.user_id == user.id).one_or_none()
    if not profile:
        profile = CustomerProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _validate_tag_ids(db: Session, tag_ids: list[int]) -> list[ValueTag]:
    if not tag_ids:
        return []
    tags = db.query(ValueTag).filter(ValueTag.id.in_(tag_ids), ValueTag.is_active.is_(True)).all()
    found_ids = {t.id for t in tags}
    missing = [tid for tid in tag_ids if tid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or inactive tag ids: {missing}",
        )
    return tags


@router.get("/me", response_model=CustomerProfilePublic)
def get_my_profile(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerProfile:
    return _get_or_create_profile(db, user)


@router.patch("/me", response_model=CustomerProfilePublic)
def update_my_profile(
    payload: CustomerProfileUpdate,
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> CustomerProfile:
    profile = _get_or_create_profile(db, user)

    if payload.primary_focus_tag_id is not None:
        _validate_tag_ids(db, [payload.primary_focus_tag_id])
        profile.primary_focus_tag_id = payload.primary_focus_tag_id

    if payload.secondary_focus_tag_ids is not None:
        _validate_tag_ids(db, payload.secondary_focus_tag_ids)
        db.query(CustomerSecondaryFocus).filter(CustomerSecondaryFocus.profile_id == profile.id).delete()
        db.flush()
        for tid in set(payload.secondary_focus_tag_ids):
            db.add(CustomerSecondaryFocus(profile_id=profile.id, tag_id=tid))

    if payload.rewards_preferences is not None:
        profile.rewards_preferences = payload.rewards_preferences.model_dump(exclude_none=True)

    db.commit()
    grant_onboarding_complete_if_eligible(db, user=user)
    db.commit()
    db.refresh(profile)

    try:
        from app.services.vector_index import upsert_customer_embedding

        upsert_customer_embedding(db, user.id)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Customer embedding refresh failed after profile update: %s", exc)
        db.rollback()

    db.refresh(profile)
    return profile
