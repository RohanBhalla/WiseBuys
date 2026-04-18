from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_customer, get_db
from app.models import User
from app.schemas.recommendations import (
    ComparablePurchase,
    RecommendationItem,
    SpendingInsight,
    VendorProductSummary,
)
from app.services.recommendations import recommend_for_user, spending_insights

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/me", response_model=list[RecommendationItem])
def my_recommendations(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[RecommendationItem]:
    recs = recommend_for_user(db, user, limit=limit)
    return [
        RecommendationItem(
            product=VendorProductSummary.model_validate(r.product),
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


insights_router = APIRouter(prefix="/api/insights", tags=["insights"])


@insights_router.get("/spending", response_model=list[SpendingInsight])
def my_spending(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> list[SpendingInsight]:
    return [SpendingInsight(**row) for row in spending_insights(db, user)]
