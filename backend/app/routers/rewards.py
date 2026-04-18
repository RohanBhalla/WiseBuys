from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import get_current_admin, get_current_customer, get_db
from app.models import User
from app.schemas.rewards import (
    AdminAdjustmentRequest,
    RewardEventPublic,
    RewardSummary,
)
from app.services.rewards import (
    admin_adjust,
    get_balance,
    grant_aligned_purchases_for_user,
    list_events,
)

router = APIRouter(prefix="/api/rewards", tags=["rewards"])


@router.get("/me", response_model=RewardSummary)
def my_rewards(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RewardSummary:
    balance = get_balance(db, user)
    events = list_events(db, user, limit=limit, offset=offset)
    return RewardSummary(
        balance=balance,
        events=[RewardEventPublic.model_validate(e) for e in events],
    )


@router.post("/me/recompute", response_model=RewardSummary)
def recompute_my_rewards(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> RewardSummary:
    """Idempotently sweep recent purchases for aligned-purchase rewards."""

    grant_aligned_purchases_for_user(db, user)
    db.commit()
    return RewardSummary(
        balance=get_balance(db, user),
        events=[RewardEventPublic.model_validate(e) for e in list_events(db, user)],
    )


admin_router = APIRouter(prefix="/api/admin/rewards", tags=["admin", "rewards"])


@admin_router.post("/adjust", response_model=RewardEventPublic, status_code=status.HTTP_201_CREATED)
def admin_adjustment(
    payload: AdminAdjustmentRequest,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> RewardEventPublic:
    target = db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    result = admin_adjust(
        db,
        user=target,
        points=payload.points,
        description=payload.description,
        dedupe_key=payload.dedupe_key,
    )
    if not result.granted or result.event is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Adjustment not applied: {result.reason}",
        )
    db.commit()
    db.refresh(result.event)
    return RewardEventPublic.model_validate(result.event)
