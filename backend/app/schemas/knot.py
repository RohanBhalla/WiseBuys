from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class KnotMerchantLite(BaseModel):
    """Subset of Knot List Merchants response for the UI."""

    id: int
    name: str | None = None
    logo: str | None = None
    category: str | None = None


class CreateSessionRequest(BaseModel):
    merchant_id: int
    metadata: dict[str, str] | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    client_id: str
    environment: str
    merchant_id: int
    external_user_id: str


class MerchantAccountPublic(BaseModel):
    id: int
    knot_merchant_id: int
    merchant_name: str | None
    connection_status: str
    last_synced_at: datetime | None = None
    authenticated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LineItemPublic(BaseModel):
    id: int
    name: str
    description: str | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    total: Decimal | None = None
    seller_name: str | None = None

    model_config = {"from_attributes": True}


class PurchasePublic(BaseModel):
    id: int
    knot_transaction_id: str
    knot_merchant_id: int
    merchant_name: str | None
    occurred_at: datetime | None = None
    order_status: str | None = None
    currency: str | None = None
    total: Decimal | None = None
    url: str | None = None
    line_items: list[LineItemPublic] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class KnotPurchasesMeta(BaseModel):
    """Row count for paginated ``GET /api/knot/purchases`` (same filters)."""

    total: int


class SyncRequest(BaseModel):
    merchant_id: int


class SyncResponse(BaseModel):
    merchant_id: int
    pages_fetched: int
    transactions_seen: int
    transactions_persisted: int
    rewards_events_granted: int = 0
    rewards_points_awarded: int = 0


class WebhookAck(BaseModel):
    received: bool = True
    event: str | None = None


class DevSimulateLinkRequest(BaseModel):
    """Body for POST /api/knot/dev/simulate-link.

    Triggers Knot's `POST /development/accounts/link` so the configured
    webhook receives `AUTHENTICATED` followed (optionally) by
    `NEW_TRANSACTIONS_AVAILABLE` and `UPDATED_TRANSACTIONS_AVAILABLE`.
    """

    merchant_id: int
    new_transactions: bool = True
    updated_transactions: bool = False


class DevSimulateDisconnectRequest(BaseModel):
    """Body for POST /api/knot/dev/simulate-disconnect.

    Triggers Knot's `POST /development/accounts/disconnect` so the
    configured webhook receives `ACCOUNT_LOGIN_REQUIRED`.
    """

    merchant_id: int


class DevSimulateAck(BaseModel):
    requested: str
    merchant_id: int
    external_user_id: str
    knot_response: dict | None = None
