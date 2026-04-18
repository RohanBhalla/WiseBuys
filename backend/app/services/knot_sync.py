from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.knot.client import KnotClient
from app.models import KnotLineItem, KnotMerchantAccount, KnotPurchase, User
from app.services import rewards as rewards_service

# Per Knot docs we usually exclude these for spending insights and matching.
EXCLUDED_ORDER_STATUSES = {"CANCELLED", "REFUNDED", "RETURNED"}


def external_user_id_for(user: User | int) -> str:
    user_id = user.id if isinstance(user, User) else user
    return f"wb-user-{user_id}"


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def upsert_merchant_account(
    db: Session,
    *,
    user: User,
    knot_merchant_id: int,
    merchant_name: str | None = None,
    connection_status: str = "connected",
    authenticated: bool = False,
) -> KnotMerchantAccount:
    account = (
        db.query(KnotMerchantAccount)
        .filter(
            KnotMerchantAccount.user_id == user.id,
            KnotMerchantAccount.knot_merchant_id == knot_merchant_id,
        )
        .one_or_none()
    )
    now = datetime.now(timezone.utc)
    if not account:
        account = KnotMerchantAccount(
            user_id=user.id,
            external_user_id=external_user_id_for(user),
            knot_merchant_id=knot_merchant_id,
            merchant_name=merchant_name,
            connection_status=connection_status,
            authenticated_at=now if authenticated else None,
        )
        db.add(account)
    else:
        if merchant_name and not account.merchant_name:
            account.merchant_name = merchant_name
        account.connection_status = connection_status
        if authenticated:
            account.authenticated_at = now
    db.flush()
    return account


def _persist_transaction(
    db: Session,
    *,
    user: User,
    knot_merchant_id: int,
    merchant_name: str | None,
    txn: dict,
) -> KnotPurchase | None:
    transaction_id = txn.get("id")
    if not transaction_id:
        return None

    purchase = (
        db.query(KnotPurchase)
        .filter(KnotPurchase.knot_transaction_id == transaction_id)
        .one_or_none()
    )

    price = txn.get("price") or {}
    purchase_data = dict(
        user_id=user.id,
        knot_transaction_id=transaction_id,
        knot_merchant_id=knot_merchant_id,
        merchant_name=merchant_name,
        external_id=txn.get("external_id"),
        occurred_at=_parse_dt(txn.get("datetime")),
        order_status=txn.get("order_status"),
        currency=price.get("currency"),
        sub_total=_to_decimal(price.get("sub_total")),
        total=_to_decimal(price.get("total")),
        url=txn.get("url"),
        raw=txn,
    )

    if purchase is None:
        purchase = KnotPurchase(**purchase_data)
        db.add(purchase)
        db.flush()
    else:
        for key, value in purchase_data.items():
            setattr(purchase, key, value)
        db.query(KnotLineItem).filter(KnotLineItem.purchase_id == purchase.id).delete()
        db.flush()

    for product in txn.get("products") or []:
        ppr = product.get("price") or {}
        seller = product.get("seller") or {}
        db.add(
            KnotLineItem(
                purchase_id=purchase.id,
                external_id=product.get("external_id"),
                name=product.get("name") or "(unnamed item)",
                description=product.get("description"),
                url=product.get("url"),
                image_url=product.get("image_url"),
                quantity=product.get("quantity"),
                unit_price=_to_decimal(ppr.get("unit_price")),
                sub_total=_to_decimal(ppr.get("sub_total")),
                total=_to_decimal(ppr.get("total")),
                seller_name=seller.get("name") if isinstance(seller, dict) else None,
                raw=product,
            )
        )
    return purchase


def sync_transactions_for_account(
    db: Session,
    knot: KnotClient,
    *,
    user: User,
    knot_merchant_id: int,
    page_limit: int = 100,
    max_pages: int = 50,
) -> dict:
    """Pull all available pages of transactions and upsert them.

    Returns a small summary dict for logging / API responses.
    """

    account = upsert_merchant_account(
        db, user=user, knot_merchant_id=knot_merchant_id
    )

    cursor = account.sync_cursor
    pages = 0
    total_seen = 0
    total_persisted = 0
    last_merchant_name = account.merchant_name

    while pages < max_pages:
        response = knot.sync_transactions(
            external_user_id=account.external_user_id,
            merchant_id=knot_merchant_id,
            cursor=cursor,
            limit=page_limit,
        )
        pages += 1
        transactions = response.get("transactions") or []
        merchant = response.get("merchant") or {}
        if merchant.get("name"):
            last_merchant_name = merchant["name"]

        for txn in transactions:
            total_seen += 1
            persisted = _persist_transaction(
                db,
                user=user,
                knot_merchant_id=knot_merchant_id,
                merchant_name=last_merchant_name,
                txn=txn,
            )
            if persisted is not None:
                total_persisted += 1

        next_cursor = response.get("next_cursor")
        if not next_cursor:
            cursor = None
            break
        cursor = next_cursor

    account.sync_cursor = cursor
    account.last_synced_at = datetime.now(timezone.utc)
    if last_merchant_name:
        account.merchant_name = last_merchant_name

    link_result = rewards_service.grant_account_linked(
        db,
        user=user,
        knot_merchant_id=knot_merchant_id,
        merchant_name=last_merchant_name,
    )
    rewards_summary = rewards_service.grant_aligned_purchases_for_user(db, user)
    events_granted = rewards_summary["events_granted"]
    points_awarded = rewards_summary["points_awarded"]
    if link_result.granted and link_result.event is not None:
        events_granted += 1
        points_awarded += link_result.event.points
    db.commit()

    return {
        "merchant_id": knot_merchant_id,
        "pages_fetched": pages,
        "transactions_seen": total_seen,
        "transactions_persisted": total_persisted,
        "rewards_events_granted": events_granted,
        "rewards_points_awarded": points_awarded,
    }
