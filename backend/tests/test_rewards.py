from __future__ import annotations

import os

import pytest

from app.knot_deps import get_knot
from app.main import app
from tests.conftest import auth_headers
from tests.fakes.knot import FakeKnotClient


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


def _admin_headers(client):
    return auth_headers(client, "admin@wisebuys.example.com", "AdminPass123!")


def _tag_id(client, slug: str) -> int:
    return next(t["id"] for t in client.get("/api/tags").json() if t["slug"] == slug)


def _seed_approved_vendor(client, *, email, company, allowed_slugs):
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "VendorPass1!", "role": "vendor"},
    )
    vendor_headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    requested = [_tag_id(client, s) for s in allowed_slugs]
    res = client.post(
        "/api/vendors/applications",
        headers=vendor_headers,
        json={
            "company_legal_name": company,
            "company_website": "https://example.com",
            "contact_email": email,
            "country": "US",
            "narrative": "Values-aligned vendor.",
            "evidence_urls": ["https://example.com/proof"],
            "requested_tag_ids": requested,
        },
    )
    application_id = res.json()["id"]
    admin_headers = _admin_headers(client)
    client.post(
        f"/api/admin/applications/{application_id}/decision",
        headers=admin_headers,
        json={"status": "approved", "allowed_tag_ids": requested},
    )
    return vendor_headers


def test_onboarding_grants_bonus_once(client, fake_knot):
    headers = auth_headers(client, "rew-onboard@example.com", "ShopperPass1!", role="customer")
    primary = _tag_id(client, "sustainability")
    secondary = _tag_id(client, "black_owned")

    # First completion: should grant bonus
    res = client.patch(
        "/api/customers/me",
        headers=headers,
        json={
            "primary_focus_tag_id": primary,
            "secondary_focus_tag_ids": [secondary],
        },
    )
    assert res.status_code == 200, res.text

    summary = client.get("/api/rewards/me", headers=headers).json()
    assert summary["balance"] == 50
    types = [e["event_type"] for e in summary["events"]]
    assert types.count("onboarding_complete") == 1

    # Idempotent: re-saving the profile doesn't re-grant
    client.patch(
        "/api/customers/me",
        headers=headers,
        json={"secondary_focus_tag_ids": [secondary]},
    )
    summary2 = client.get("/api/rewards/me", headers=headers).json()
    assert summary2["balance"] == 50
    assert [e for e in summary2["events"] if e["event_type"] == "onboarding_complete"].__len__() == 1


def test_sync_grants_link_bonus_and_aligned_purchase(client, fake_knot):
    headers = auth_headers(client, "rew-shop@example.com", "ShopperPass1!", role="customer")
    primary = _tag_id(client, "sustainability")
    client.patch(
        "/api/customers/me",
        headers=headers,
        json={"primary_focus_tag_id": primary, "secondary_focus_tag_ids": [_tag_id(client, "black_owned")]},
    )
    _seed_approved_vendor(
        client, email="rew-vendor@example.com", company="DoorDash", allowed_slugs=["sustainability"]
    )

    fake_knot.pages = [
        {
            "merchant": {"id": 19, "name": "DoorDash"},
            "transactions": [
                {
                    "id": "txn-rw-1",
                    "datetime": "2025-02-01T12:00:00+00:00",
                    "order_status": "DELIVERED",
                    "price": {"total": "42.00", "currency": "USD"},
                    "products": [
                        {
                            "external_id": "p1",
                            "name": "Some Item",
                            "quantity": 1,
                            "price": {"sub_total": "42.00", "total": "42.00", "unit_price": "42.00"},
                        }
                    ],
                },
                {
                    "id": "txn-rw-2",
                    "datetime": "2025-02-02T12:00:00+00:00",
                    "order_status": "CANCELLED",
                    "price": {"total": "10.00", "currency": "USD"},
                    "products": [],
                },
            ],
            "next_cursor": None,
        }
    ]

    res = client.post("/api/knot/sync", headers=headers, json={"merchant_id": 19})
    assert res.status_code == 200, res.text
    body = res.json()
    # 100 (account_linked) + 50 (onboarding) + 42 (aligned purchase)
    assert body["rewards_events_granted"] == 2  # link + aligned (onboarding granted earlier)
    assert body["rewards_points_awarded"] == 100 + 42

    summary = client.get("/api/rewards/me", headers=headers).json()
    assert summary["balance"] == 50 + 100 + 42
    types = [e["event_type"] for e in summary["events"]]
    assert "account_linked" in types
    assert "aligned_purchase" in types

    # Re-sync: dedupe everything
    fake_knot.pages = []
    res2 = client.post("/api/knot/sync", headers=headers, json={"merchant_id": 19})
    assert res2.status_code == 200
    assert res2.json()["rewards_events_granted"] == 0
    summary2 = client.get("/api/rewards/me", headers=headers).json()
    assert summary2["balance"] == 50 + 100 + 42


def test_authenticated_webhook_grants_link_bonus(client, fake_knot):
    headers = auth_headers(client, "rew-hook@example.com", "ShopperPass1!", role="customer")
    me = client.get("/api/auth/me", headers=headers).json()
    payload = {
        "event": "AUTHENTICATED",
        "session_id": "sess-r1",
        "external_user_id": f"wb-user-{me['id']}",
        "merchant": {"id": 19, "name": "DoorDash"},
    }
    res = client.post("/api/knot/webhooks", json=payload)
    assert res.status_code == 200

    summary = client.get("/api/rewards/me", headers=headers).json()
    assert summary["balance"] == 100
    assert summary["events"][0]["event_type"] == "account_linked"


def test_admin_adjustment_credits_balance(client, fake_knot):
    headers = auth_headers(client, "rew-target@example.com", "ShopperPass1!", role="customer")
    me = client.get("/api/auth/me", headers=headers).json()

    admin_headers = _admin_headers(client)
    res = client.post(
        "/api/admin/rewards/adjust",
        headers=admin_headers,
        json={
            "user_id": me["id"],
            "points": 75,
            "description": "Welcome credit",
            "dedupe_key": "welcome-1",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["points"] == 75

    # Same dedupe_key -> 409
    res2 = client.post(
        "/api/admin/rewards/adjust",
        headers=admin_headers,
        json={
            "user_id": me["id"],
            "points": 75,
            "description": "Welcome credit",
            "dedupe_key": "welcome-1",
        },
    )
    assert res2.status_code == 409

    summary = client.get("/api/rewards/me", headers=headers).json()
    assert summary["balance"] == 75
