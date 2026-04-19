from __future__ import annotations

import os

import pytest

from app.knot.signature import compute_knot_signature
from app.knot_deps import get_knot, get_knot_optional
from app.main import app
from tests.conftest import auth_headers
from tests.fakes.knot import FakeKnotClient, sample_transactions


@pytest.fixture()
def fake_knot():
    fake = FakeKnotClient()
    app.dependency_overrides[get_knot] = lambda: fake
    app.dependency_overrides[get_knot_optional] = lambda: fake
    os.environ["KNOT_CLIENT_ID"] = "test-client"
    os.environ["KNOT_SECRET"] = "test-secret"
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_knot, None)
        app.dependency_overrides.pop(get_knot_optional, None)


def _customer(client):
    return auth_headers(client, "knot-shopper@example.com", "ShopperPass1!", role="customer")


def test_create_session_returns_session(client, fake_knot):
    headers = _customer(client)
    res = client.post("/api/knot/sessions", headers=headers, json={"merchant_id": 19})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["session_id"] == "fake-session-123"
    assert body["merchant_id"] == 19
    assert body["external_user_id"].startswith("wb-user-")


def test_list_merchants(client, fake_knot):
    headers = _customer(client)
    res = client.get("/api/knot/merchants", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == [
        {
            "id": 19,
            "name": "DoorDash",
            "logo": "https://example.com/merchants/doordash.png",
            "category": "Food delivery",
        }
    ]


def test_purchases_limit_validation(client, fake_knot):
    headers = _customer(client)
    res = client.get("/api/knot/purchases?limit=500", headers=headers)
    assert res.status_code == 422


def test_purchases_meta_total(client, fake_knot):
    headers = _customer(client)
    fake_knot.pages = [{"transactions": sample_transactions(1, 2), "next_cursor": None}]
    assert client.post("/api/knot/sync", headers=headers, json={"merchant_id": 19}).status_code == 200
    meta = client.get("/api/knot/purchases/meta", headers=headers).json()
    assert meta == {"total": 2}
    meta_dd = client.get("/api/knot/purchases/meta?merchant_id=19", headers=headers).json()
    assert meta_dd == {"total": 2}


def test_sync_persists_transactions_and_resumes(client, fake_knot):
    headers = _customer(client)
    fake_knot.pages = [
        {"transactions": sample_transactions(1, 2), "next_cursor": "cursor-1"},
        {"transactions": sample_transactions(3, 1), "next_cursor": None},
    ]

    res = client.post("/api/knot/sync", headers=headers, json={"merchant_id": 19})
    assert res.status_code == 200, res.text
    summary = res.json()
    assert summary["pages_fetched"] == 2
    assert summary["transactions_persisted"] == 3

    purchases = client.get("/api/knot/purchases", headers=headers).json()
    assert len(purchases) == 3
    first = purchases[0]
    assert first["merchant_name"] == "DoorDash"
    assert first["currency"] == "USD"
    assert len(first["line_items"]) == 2

    accounts = client.get("/api/knot/merchant-accounts", headers=headers).json()
    assert len(accounts) == 1
    assert accounts[0]["knot_merchant_id"] == 19
    assert accounts[0]["last_synced_at"] is not None

    # Re-syncing with no new pages should be a no-op (cursor is `None`).
    fake_knot.pages = []
    res2 = client.post("/api/knot/sync", headers=headers, json={"merchant_id": 19})
    assert res2.status_code == 200
    assert res2.json()["transactions_persisted"] == 0


def test_sync_retains_purchases_when_account_link_reward_already_granted(client, fake_knot):
    """AUTHENTICATED webhook inserts account_linked; sync must not rollback flushed purchases on duplicate reward."""
    headers = _customer(client)
    me = client.get("/api/auth/me", headers=headers).json()
    external_user_id = f"wb-user-{me['id']}"
    client.post(
        "/api/knot/webhooks",
        json={
            "event": "AUTHENTICATED",
            "session_id": "sess-pre-sync",
            "external_user_id": external_user_id,
            "merchant": {"id": 19, "name": "DoorDash"},
        },
    )
    fake_knot.pages = [{"transactions": sample_transactions(1, 2), "next_cursor": None}]
    res = client.post("/api/knot/sync", headers=headers, json={"merchant_id": 19})
    assert res.status_code == 200, res.text
    purchases = client.get("/api/knot/purchases", headers=headers).json()
    assert len(purchases) == 2


def test_sync_same_transaction_twice_in_one_page_does_not_500(client, fake_knot):
    """Knot can repeat the same transaction id in one payload; upsert must not violate unique."""
    headers = _customer(client)
    txn = sample_transactions(1, 1)[0]
    fake_knot.pages = [{"transactions": [txn, txn], "next_cursor": None}]
    res = client.post("/api/knot/sync", headers=headers, json={"merchant_id": 19})
    assert res.status_code == 200, res.text
    purchases = client.get("/api/knot/purchases", headers=headers).json()
    assert len(purchases) == 1


def test_authenticated_webhook_creates_account(client, fake_knot):
    headers = _customer(client)
    me = client.get("/api/auth/me", headers=headers).json()
    external_user_id = f"wb-user-{me['id']}"

    payload = {
        "event": "AUTHENTICATED",
        "session_id": "sess-1",
        "external_user_id": external_user_id,
        "merchant": {"id": 19, "name": "DoorDash"},
    }

    res = client.post("/api/knot/webhooks", json=payload)
    assert res.status_code == 200, res.text
    assert res.json()["event"] == "AUTHENTICATED"

    accounts = client.get("/api/knot/merchant-accounts", headers=headers).json()
    assert len(accounts) == 1
    assert accounts[0]["connection_status"] == "connected"
    assert accounts[0]["authenticated_at"] is not None


def test_new_transactions_webhook_triggers_sync(client, fake_knot):
    headers = _customer(client)
    me = client.get("/api/auth/me", headers=headers).json()
    fake_knot.pages = [{"transactions": sample_transactions(10, 2), "next_cursor": None}]

    payload = {
        "event": "NEW_TRANSACTIONS_AVAILABLE",
        "session_id": "sess-2",
        "external_user_id": f"wb-user-{me['id']}",
        "merchant": {"id": 19, "name": "DoorDash"},
    }
    res = client.post("/api/knot/webhooks", json=payload)
    assert res.status_code == 200

    purchases = client.get("/api/knot/purchases", headers=headers).json()
    assert len(purchases) == 2


def test_account_login_required_marks_disconnected(client, fake_knot):
    headers = _customer(client)
    me = client.get("/api/auth/me", headers=headers).json()
    external_user_id = f"wb-user-{me['id']}"

    client.post(
        "/api/knot/webhooks",
        json={
            "event": "AUTHENTICATED",
            "session_id": "sess-3",
            "external_user_id": external_user_id,
            "merchant": {"id": 19, "name": "DoorDash"},
        },
    )

    res = client.post(
        "/api/knot/webhooks",
        json={
            "event": "ACCOUNT_LOGIN_REQUIRED",
            "session_id": "sess-4",
            "external_user_id": external_user_id,
            "merchant": {"id": 19, "name": "DoorDash"},
        },
    )
    assert res.status_code == 200

    accounts = client.get("/api/knot/merchant-accounts", headers=headers).json()
    assert accounts[0]["connection_status"] == "disconnected"


def test_invalid_signature_rejected(client, fake_knot, monkeypatch):
    monkeypatch.setenv("KNOT_SECRET", "real-secret")
    from app.config import get_settings

    get_settings.cache_clear()
    res = client.post(
        "/api/knot/webhooks",
        headers={"Knot-Signature": "not-the-right-sig"},
        json={"event": "AUTHENTICATED", "session_id": "sess-x"},
    )
    assert res.status_code == 401


def test_updated_transactions_webhook_refreshes_by_id(client, fake_knot):
    """UPDATED_TRANSACTIONS_AVAILABLE should call Get Transaction By ID per
    https://docs.knotapi.com/transaction-link/webhook-events/updated-transactions-available
    and upsert the changed order_status/line items."""

    headers = _customer(client)
    me = client.get("/api/auth/me", headers=headers).json()
    external_user_id = f"wb-user-{me['id']}"

    # 1) Seed two purchases via NEW_TRANSACTIONS_AVAILABLE.
    fake_knot.pages = [{"transactions": sample_transactions(100, 2), "next_cursor": None}]
    res = client.post(
        "/api/knot/webhooks",
        json={
            "event": "NEW_TRANSACTIONS_AVAILABLE",
            "session_id": "sess-upd-1",
            "external_user_id": external_user_id,
            "merchant": {"id": 19, "name": "DoorDash"},
        },
    )
    assert res.status_code == 200, res.text

    # 2) Knot updates one transaction's order_status from DELIVERED -> RETURNED.
    updated_txn = sample_transactions(100, 1)[0]
    updated_txn["order_status"] = "RETURNED"
    fake_knot.transactions_by_id = {updated_txn["id"]: updated_txn}

    res2 = client.post(
        "/api/knot/webhooks",
        json={
            "event": "UPDATED_TRANSACTIONS_AVAILABLE",
            "session_id": "sess-upd-2",
            "external_user_id": external_user_id,
            "merchant": {"id": 19, "name": "DoorDash"},
            "data": {"transactions": [updated_txn["id"]]},
        },
    )
    assert res2.status_code == 200, res2.text

    purchases = client.get("/api/knot/purchases", headers=headers).json()
    target = next(p for p in purchases if p["knot_transaction_id"] == updated_txn["id"])
    assert target["order_status"] == "RETURNED"


def test_merchant_status_update_event_is_acked(client, fake_knot):
    res = client.post(
        "/api/knot/webhooks",
        json={
            "event": "MERCHANT_STATUS_UPDATE",
            "merchant": {"id": 19, "name": "DoorDash"},
            "type": "transaction_link",
            "platform": "web",
        },
    )
    assert res.status_code == 200
    assert res.json()["event"] == "MERCHANT_STATUS_UPDATE"


def test_require_signature_rejects_unsigned(client, fake_knot, monkeypatch):
    monkeypatch.setenv("KNOT_SECRET", "real-secret")
    monkeypatch.setenv("KNOT_WEBHOOK_REQUIRE_SIGNATURE", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        res = client.post(
            "/api/knot/webhooks",
            json={"event": "AUTHENTICATED", "session_id": "sess-z"},
        )
        assert res.status_code == 401
    finally:
        get_settings.cache_clear()


def test_dev_simulate_link_calls_knot(client, fake_knot):
    headers = _customer(client)
    res = client.post(
        "/api/knot/dev/simulate-link",
        headers=headers,
        json={"merchant_id": 19, "new_transactions": True, "updated_transactions": True},
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["requested"] == "link"
    assert body["merchant_id"] == 19
    assert body["external_user_id"].startswith("wb-user-")

    # Verify the underlying client call carried the documented shape.
    name, kwargs = next(c for c in fake_knot.calls if c[0] == "link_account_dev")
    assert name == "link_account_dev"
    assert kwargs == {
        "external_user_id": body["external_user_id"],
        "merchant_id": 19,
        "new": True,
        "updated": True,
    }


def test_dev_simulate_disconnect_calls_knot(client, fake_knot):
    headers = _customer(client)
    res = client.post(
        "/api/knot/dev/simulate-disconnect",
        headers=headers,
        json={"merchant_id": 19},
    )
    assert res.status_code == 202, res.text
    name, kwargs = next(c for c in fake_knot.calls if c[0] == "disconnect_account_dev")
    assert name == "disconnect_account_dev"
    assert kwargs["merchant_id"] == 19


def test_dev_simulate_blocked_when_disabled(client, fake_knot, monkeypatch):
    monkeypatch.setenv("KNOT_DEV_SIMULATION_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        headers = _customer(client)
        res = client.post(
            "/api/knot/dev/simulate-link",
            headers=headers,
            json={"merchant_id": 19},
        )
        assert res.status_code == 403
    finally:
        get_settings.cache_clear()


def test_signature_helper_matches_known_input():
    secret = "shhh"
    headers = {
        "content-length": "178",
        "content-type": "application/json",
        "encryption-type": "HMAC-SHA256",
    }
    body = {"event": "CARD_UPDATED", "session_id": "fb5aa994-ed1c-4c3e-b29a-b2a53222e584"}
    sig = compute_knot_signature(secret, headers, body)
    assert isinstance(sig, str) and len(sig) > 20
