from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.knot.client import KnotClient, KnotError
from app.knot.signature import verify_knot_signature
from app.knot_deps import get_knot_optional
from app.models import KnotMerchantAccount, User
from app.schemas.knot import WebhookAck
from app.services.knot_sync import (
    refresh_transaction_by_id,
    sync_transactions_for_account,
    upsert_merchant_account,
)
from app.services.rewards import grant_account_linked

router = APIRouter(prefix="/api/knot", tags=["knot-webhooks"])

logger = logging.getLogger(__name__)

# Events that don't carry a session_id are excluded from the signing hash map
# per https://docs.knotapi.com/webhooks#webhook-verification.
EVENTS_WITHOUT_SESSION_ID = {"MERCHANT_STATUS_UPDATE"}


def _user_for_external_id(db: Session, external_user_id: str | None) -> User | None:
    if not external_user_id or not external_user_id.startswith("wb-user-"):
        return None
    try:
        user_id = int(external_user_id[len("wb-user-") :])
    except ValueError:
        return None
    return db.get(User, user_id)


def _extract_updated_transaction_ids(payload: dict[str, Any]) -> list[str]:
    """Pull out the array of transaction IDs from the
    UPDATED_TRANSACTIONS_AVAILABLE webhook. Knot wraps the list in `data`,
    but we accept a few shapes defensively."""

    def _coerce(items: Any) -> list[str]:
        out: list[str] = []
        if not isinstance(items, list):
            return out
        for item in items:
            if isinstance(item, str) and item:
                out.append(item)
            elif isinstance(item, dict):
                tid = item.get("id") or item.get("transaction_id")
                if tid:
                    out.append(str(tid))
        return out

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    candidates = [
        data.get("transactions"),
        data.get("transaction_ids"),
        payload.get("transactions"),
        payload.get("transaction_ids"),
    ]
    for c in candidates:
        ids = _coerce(c)
        if ids:
            return ids
    return []


@router.post("/webhooks", response_model=WebhookAck)
async def knot_webhook(
    request: Request,
    db: Session = Depends(get_db),
    knot: KnotClient | None = Depends(get_knot_optional),
) -> WebhookAck:
    """Webhook receiver for Knot events.

    Knot retries up to two times on non-2xx within ~10s, so this endpoint
    catches downstream failures and ACKs once we've durably recorded the
    event intent. See https://docs.knotapi.com/webhooks.
    """

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    settings = get_settings()
    headers = {k: v for k, v in request.headers.items()}
    provided_sig = headers.get("knot-signature")
    event = payload.get("event")

    body_fields: dict[str, Any] = {"event": event}
    if event not in EVENTS_WITHOUT_SESSION_ID:
        body_fields["session_id"] = payload.get("session_id")

    if settings.knot_secret and provided_sig:
        valid = verify_knot_signature(
            provided_signature=provided_sig,
            secret=settings.knot_secret,
            headers=headers,
            body_fields=body_fields,
        )
        if not valid:
            logger.warning("Rejected Knot webhook with invalid signature (event=%s)", event)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Knot signature"
            )
    elif settings.knot_webhook_require_signature:
        logger.warning(
            "Rejected Knot webhook missing signature while require_signature=True (event=%s)",
            event,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Knot-Signature header",
        )

    external_user_id = payload.get("external_user_id")
    merchant = payload.get("merchant") or {}
    knot_merchant_id = merchant.get("id") if isinstance(merchant, dict) else None
    merchant_name = merchant.get("name") if isinstance(merchant, dict) else None

    user = _user_for_external_id(db, external_user_id)

    logger.info(
        "Knot webhook received: event=%s external_user_id=%s merchant_id=%s known_user=%s",
        event,
        external_user_id,
        knot_merchant_id,
        bool(user),
    )

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
        if knot is None:
            logger.warning(
                "NEW_TRANSACTIONS_AVAILABLE for user=%s merchant=%s but Knot client not configured;"
                " skipping sync.",
                user.id,
                knot_merchant_id,
            )
        else:
            try:
                sync_transactions_for_account(
                    db, knot, user=user, knot_merchant_id=knot_merchant_id
                )
            except KnotError as exc:
                # ACK to avoid Knot retry loops; we'll catch up on the next sync.
                logger.warning(
                    "Knot sync after NEW_TRANSACTIONS_AVAILABLE failed: %s", exc
                )

    elif event == "UPDATED_TRANSACTIONS_AVAILABLE" and user and knot_merchant_id is not None:
        ids = _extract_updated_transaction_ids(payload)
        if not ids:
            logger.info(
                "UPDATED_TRANSACTIONS_AVAILABLE without transaction ids; falling back to a sync."
            )
            if knot is not None:
                try:
                    sync_transactions_for_account(
                        db, knot, user=user, knot_merchant_id=knot_merchant_id
                    )
                except KnotError as exc:
                    logger.warning("Fallback sync failed: %s", exc)
        else:
            if knot is None:
                logger.warning(
                    "UPDATED_TRANSACTIONS_AVAILABLE received but Knot client not configured;"
                    " cannot fetch %d transaction(s).",
                    len(ids),
                )
            else:
                refreshed = 0
                for tid in ids:
                    try:
                        if (
                            refresh_transaction_by_id(
                                db,
                                knot,
                                user=user,
                                transaction_id=tid,
                                knot_merchant_id=knot_merchant_id,
                            )
                            is not None
                        ):
                            refreshed += 1
                    except KnotError as exc:
                        logger.warning(
                            "Failed to refresh transaction %s: %s", tid, exc
                        )
                if refreshed:
                    db.commit()
                logger.info(
                    "Refreshed %d/%d updated transactions for user=%s merchant=%s",
                    refreshed,
                    len(ids),
                    user.id,
                    knot_merchant_id,
                )

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

    elif event == "MERCHANT_STATUS_UPDATE":
        # Informational only — refreshing the local merchant cache happens on
        # the next /api/knot/merchants call.
        logger.info(
            "MERCHANT_STATUS_UPDATE received: merchant=%s payload_keys=%s",
            knot_merchant_id,
            sorted((payload or {}).keys()),
        )

    else:
        logger.info("Knot webhook ignored: event=%s known_user=%s", event, bool(user))

    return WebhookAck(received=True, event=event)
