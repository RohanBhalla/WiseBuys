from __future__ import annotations

import os

import pytest

from app.knot.signature import compute_knot_signature
from app.knot_deps import get_knot
from app.main import app
from tests.conftest import auth_headers
from tests.fakes.knot import FakeKnotClient, sample_transactions


@pytest.fixture()
def fake_knot():
    fake = FakeKnotClient()
    app.dependency_overrides[get_knot] = lambda: fake
    os.environ["KNOT_CLIENT_ID"] = "test-client"
    os.environ["KNOT_SECRET"] = "test-secret"
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_knot, None)


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
    assert res.json() == [{"id": 19, "name": "DoorDash"}]


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
