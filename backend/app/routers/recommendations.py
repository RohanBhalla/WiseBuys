from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_customer, get_db
from app.models import RecommendationClick, User, VendorProduct
from app.models.vendor import VendorAllowedTag, VendorProfile
from app.schemas.recommendations import (
    ComparablePurchase,
    RecommendationClickCreate,
    RecommendationClickPublic,
    RecommendationItem,
    SpendingInsight,
    VendorProductSummary,
)
from app.schemas.tag import TagPublic
from app.services.recommendations import recommend_for_user, spending_insights


def _vendor_tags_by_user_id(db: Session, vendor_user_ids: list[int]) -> dict[int, list[TagPublic]]:
    """Map vendor user_id → approved tags (VendorAllowedTag) for UI value chips."""
    if not vendor_user_ids:
        return {}
    rows = (
        db.query(VendorProfile)
        .options(selectinload(VendorProfile.allowed_tags).selectinload(VendorAllowedTag.tag))
        .filter(VendorProfile.user_id.in_(vendor_user_ids))
        .all()
    )
    out: dict[int, list[TagPublic]] = {}
    for vp in rows:
        raw = [link.tag for link in vp.allowed_tags if getattr(link, "tag", None)]
        out[vp.user_id] = [TagPublic.model_validate(t) for t in raw]
    return out

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/me", response_model=list[RecommendationItem])
def my_recommendations(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[RecommendationItem]:
    recs = recommend_for_user(db, user, limit=limit)
    v_ids = list({r.product.vendor_user_id for r in recs})
    vendor_tag_map = _vendor_tags_by_user_id(db, v_ids)
    return [
        RecommendationItem(
            product=VendorProductSummary.model_validate(r.product).model_copy(
                update={"vendor_tags": vendor_tag_map.get(r.product.vendor_user_id, [])}
            ),
            score=r.score,
            reasons=r.reasons,
            insight=r.insight,
            comparable=(
                ComparablePurchase(
                    line_item_id=r.comparable.line_item_id,
                    name=r.comparable.name,
                    merchant_name=r.comparable.merchant_name,
                    unit_price=r.comparable.unit_price,
                    total=r.comparable.total,
                    currency=r.comparable.currency,
                    occurred_at=r.comparable.occurred_at,
                )
                if r.comparable
                else None
            ),
            evidence_line_item_ids=r.evidence_line_item_ids,
        )
        for r in recs
    ]


@router.post(
    "/clicks",
    response_model=RecommendationClickPublic,
    status_code=status.HTTP_201_CREATED,
)
def record_click(
    payload: RecommendationClickCreate,
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> RecommendationClick:
    product = db.get(VendorProduct, payload.product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    click = RecommendationClick(
        user_id=user.id,
        product_id=product.id,
        vendor_user_id=product.vendor_user_id,
        source=(payload.source or "dashboard")[:64],
    )
    db.add(click)
    db.commit()
    db.refresh(click)
    return click


insights_router = APIRouter(prefix="/api/insights", tags=["insights"])


@insights_router.get("/spending", response_model=list[SpendingInsight])
def my_spending(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> list[SpendingInsight]:
    return [SpendingInsight(**row) for row in spending_insights(db, user)]
