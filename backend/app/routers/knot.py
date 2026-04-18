from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_current_customer, get_db
from app.knot.client import KnotClient, KnotError
from app.knot_deps import get_knot
from app.models import KnotMerchantAccount, KnotPurchase, User
from app.schemas.knot import (
    CreateSessionRequest,
    CreateSessionResponse,
    KnotMerchantLite,
    MerchantAccountPublic,
    PurchasePublic,
    SyncRequest,
    SyncResponse,
)
from app.services.knot_sync import (
    external_user_id_for,
    sync_transactions_for_account,
    upsert_merchant_account,
)

router = APIRouter(prefix="/api/knot", tags=["knot"])


@router.get("/merchants", response_model=list[KnotMerchantLite])
def list_transaction_link_merchants(
    user: User = Depends(get_current_customer),
    knot: KnotClient = Depends(get_knot),
) -> list[KnotMerchantLite]:
    """Merchants available for Transaction Link (for Knot Web SDK `merchantIds`)."""
    assert user.id  # customer auth
    try:
        data = knot.list_merchants("transaction_link")
    except KnotError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.payload)
    raw = data.get("merchants") or data.get("data") or []
    out: list[KnotMerchantLite] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        mid = row.get("id")
        if mid is None:
            continue
        try:
            logo = row.get("logo")
            category = row.get("category")
            out.append(
                KnotMerchantLite(
                    id=int(mid),
                    name=row.get("name"),
                    logo=logo if isinstance(logo, str) else None,
                    category=category if isinstance(category, str) else None,
                )
            )
        except (TypeError, ValueError):
            continue
    return out


@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: CreateSessionRequest,
    user: User = Depends(get_current_customer),
    knot: KnotClient = Depends(get_knot),
) -> CreateSessionResponse:
    settings = get_settings()
    external_user_id = external_user_id_for(user)
    try:
        result = knot.create_session(
            external_user_id=external_user_id,
            session_type="transaction_link",
            metadata=payload.metadata,
        )
    except KnotError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.payload)

    session_id = result.get("session") or result.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Knot did not return a session id: {result}",
        )

    return CreateSessionResponse(
        session_id=session_id,
        client_id=settings.knot_client_id or "",
        environment=settings.knot_environment,
        merchant_id=payload.merchant_id,
        external_user_id=external_user_id,
    )


@router.get("/merchant-accounts", response_model=list[MerchantAccountPublic])
def list_merchant_accounts(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> list[KnotMerchantAccount]:
    return (
        db.query(KnotMerchantAccount)
        .filter(KnotMerchantAccount.user_id == user.id)
        .order_by(KnotMerchantAccount.created_at.desc())
        .all()
    )


@router.post("/sync", response_model=SyncResponse)
def sync_now(
    payload: SyncRequest,
    user: User = Depends(get_current_customer),
    knot: KnotClient = Depends(get_knot),
    db: Session = Depends(get_db),
) -> SyncResponse:
    upsert_merchant_account(db, user=user, knot_merchant_id=payload.merchant_id)
    db.commit()
    try:
        summary = sync_transactions_for_account(
            db, knot, user=user, knot_merchant_id=payload.merchant_id
        )
    except KnotError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.payload)
    return SyncResponse(**summary)


@router.get("/purchases", response_model=list[PurchasePublic])
def list_purchases(
    user: User = Depends(get_current_customer),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    merchant_id: int | None = None,
) -> list[KnotPurchase]:
    query = db.query(KnotPurchase).filter(KnotPurchase.user_id == user.id)
    if merchant_id is not None:
        query = query.filter(KnotPurchase.knot_merchant_id == merchant_id)
    return (
        query.order_by(KnotPurchase.occurred_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
