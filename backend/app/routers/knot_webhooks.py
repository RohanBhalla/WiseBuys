from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.knot.client import KnotClient, KnotError
from app.knot.signature import verify_knot_signature
from app.knot_deps import get_knot
from app.models import KnotMerchantAccount, User
from app.schemas.knot import WebhookAck
from app.services.knot_sync import (
    external_user_id_for,
    sync_transactions_for_account,
    upsert_merchant_account,
)
from app.services.rewards import grant_account_linked

router = APIRouter(prefix="/api/knot", tags=["knot-webhooks"])


def _user_for_external_id(db: Session, external_user_id: str | None) -> User | None:
    if not external_user_id or not external_user_id.startswith("wb-user-"):
        return None
    try:
        user_id = int(external_user_id[len("wb-user-") :])
    except ValueError:
        return None
    return db.get(User, user_id)


@router.post("/webhooks", response_model=WebhookAck)
async def knot_webhook(
    request: Request,
    db: Session = Depends(get_db),
    knot: KnotClient = Depends(get_knot),
) -> WebhookAck:
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    settings = get_settings()
    headers = {k: v for k, v in request.headers.items()}
    provided_sig = headers.get("knot-signature")
    if settings.knot_secret and provided_sig:
        valid = verify_knot_signature(
            provided_signature=provided_sig,
            secret=settings.knot_secret,
            headers=headers,
            body_fields={
                "event": payload.get("event"),
                "session_id": payload.get("session_id"),
            },
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Knot signature"
            )

    event = payload.get("event")
    external_user_id = payload.get("external_user_id")
    merchant = payload.get("merchant") or {}
    knot_merchant_id = merchant.get("id")
    merchant_name = merchant.get("name")

    user = _user_for_external_id(db, external_user_id)

    if event == "AUTHENTICATED" and user and knot_merchant_id is not None:
        upsert_merchant_account(
            db,
            user=user,
            knot_merchant_id=knot_merchant_id,
            merchant_name=merchant_name,
            connection_status="connected",
            authenticated=True,
        )
        grant_account_linked(
            db,
            user=user,
            knot_merchant_id=knot_merchant_id,
            merchant_name=merchant_name,
        )
        db.commit()

    elif event == "NEW_TRANSACTIONS_AVAILABLE" and user and knot_merchant_id is not None:
        upsert_merchant_account(
            db,
            user=user,
            knot_merchant_id=knot_merchant_id,
            merchant_name=merchant_name,
            connection_status="connected",
        )
        db.commit()
        try:
            sync_transactions_for_account(
                db, knot, user=user, knot_merchant_id=knot_merchant_id
            )
        except KnotError:
            # Knot will retry on non-200, but we want to ack so we don't double-fire.
            pass

    elif event == "UPDATED_TRANSACTIONS_AVAILABLE" and user and knot_merchant_id is not None:
        # Re-running sync covers updates with the existing cursor as well.
        try:
            sync_transactions_for_account(
                db, knot, user=user, knot_merchant_id=knot_merchant_id
            )
        except KnotError:
            pass

    elif event == "ACCOUNT_LOGIN_REQUIRED" and user and knot_merchant_id is not None:
        account = (
            db.query(KnotMerchantAccount)
            .filter(
                KnotMerchantAccount.user_id == user.id,
                KnotMerchantAccount.knot_merchant_id == knot_merchant_id,
            )
            .one_or_none()
        )
        if account:
            account.connection_status = "disconnected"
            account.updated_at = datetime.now(timezone.utc)
            db.commit()

    return WebhookAck(received=True, event=event)
