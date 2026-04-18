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


def _tag_id_by_slug(client, slug: str) -> int:
    tags = client.get("/api/tags").json()
    return next(t["id"] for t in tags if t["slug"] == slug)


def _seed_approved_vendor(client, *, email, password, company, allowed_slugs, products):
    """Register a vendor, submit an application, approve it, publish products."""

    # Vendor self-registers
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": "vendor"},
    )
    assert res.status_code in (200, 201), res.text
    vendor_token = res.json()["access_token"]
    vendor_headers = {"Authorization": f"Bearer {vendor_token}"}

    requested_tag_ids = [_tag_id_by_slug(client, s) for s in allowed_slugs]

    res = client.post(
        "/api/vendors/applications",
        headers=vendor_headers,
        json={
            "company_legal_name": company,
            "company_website": "https://example.com",
            "contact_email": email,
            "country": "US",
            "narrative": "We focus on values-aligned products.",
            "evidence_urls": ["https://example.com/proof"],
            "requested_tag_ids": requested_tag_ids,
        },
    )
    assert res.status_code in (200, 201), res.text
    application_id = res.json()["id"]

    admin_headers = _admin_headers(client)
    res = client.post(
        f"/api/admin/applications/{application_id}/decision",
        headers=admin_headers,
        json={"status": "approved", "allowed_tag_ids": requested_tag_ids},
    )
    assert res.status_code == 200, res.text

    for product in products:
        res = client.post(
            "/api/catalog/products",
            headers=vendor_headers,
            json={**product, "is_published": True},
        )
        assert res.status_code in (200, 201), res.text

    return vendor_headers


def test_recommendations_match_focus_and_purchases(client, fake_knot):
    # Customer signs up + sets focuses
    customer_headers = auth_headers(
        client, "wise-shopper@example.com", "ShopperPass1!", role="customer"
    )
    primary_id = _tag_id_by_slug(client, "sustainability")
    secondary_id = _tag_id_by_slug(client, "black_owned")

    res = client.patch(
        "/api/customers/me",
        headers=customer_headers,
        json={
            "primary_focus_tag_id": primary_id,
            "secondary_focus_tag_ids": [secondary_id],
        },
    )
    assert res.status_code == 200, res.text

    # Vendor A: matches both focuses + sells "athletic socks" (overlaps test purchase)
    _seed_approved_vendor(
        client,
        email="vendora@example.com",
        password="VendorPass1!",
        company="EcoSteps",
        allowed_slugs=["sustainability", "black_owned"],
        products=[
            {
                "name": "Bamboo Athletic Crew Socks",
                "category": "apparel",
                "currency": "USD",
                "price_hint": 14.0,
                "differentiator": "Bamboo, carbon-neutral shipping",
                "key_features": ["bamboo", "moisture-wicking"],
            }
        ],
    )

    # Vendor B: no focus overlap, generic plates
    _seed_approved_vendor(
        client,
        email="vendorb@example.com",
        password="VendorPass1!",
        company="Genericorp",
        allowed_slugs=["women_owned"],
        products=[
            {
                "name": "Paper Plates Bulk",
                "category": "everyday",
                "currency": "USD",
                "price_hint": 8.0,
                "differentiator": "Cheap and disposable",
                "key_features": ["bulk"],
            }
        ],
    )

    # Seed customer purchases via Knot sync (athletic socks)
    fake_knot.pages = [
        {
            "merchant": {"id": 19, "name": "DoorDash"},
            "transactions": [
                {
                    "id": "txn-1",
                    "datetime": "2025-01-01T12:00:00+00:00",
                    "url": None,
                    "order_status": "DELIVERED",
                    "price": {"sub_total": "22.99", "total": "22.99", "currency": "USD"},
                    "products": [
                        {
                            "external_id": "prod-1",
                            "name": "Men's Athletic Crew Socks Mid-calf",
                            "description": "athletic socks",
                            "url": None,
                            "image_url": None,
                            "quantity": 1,
                            "price": {"sub_total": "22.99", "total": "22.99", "unit_price": "22.99"},
                            "seller": None,
                            "eligibility": [],
                        }
                    ],
                }
            ],
            "next_cursor": None,
        }
    ]
    res = client.post("/api/knot/sync", headers=customer_headers, json={"merchant_id": 19})
    assert res.status_code == 200, res.text

    res = client.get("/api/recommendations/me", headers=customer_headers)
    assert res.status_code == 200, res.text
    recs = res.json()
    assert recs, "expected at least one recommendation"

    top = recs[0]
    assert "Bamboo" in top["product"]["name"]
    assert any("primary focus" in r.lower() for r in top["reasons"])
    assert any("similar to items" in r.lower() for r in top["reasons"])
    assert top["evidence_line_item_ids"], "expected line-item evidence ids"
    # Generic plates vendor should be ranked below or absent
    assert top["score"] >= recs[-1]["score"]


def test_spending_insights_aggregate_by_merchant(client, fake_knot):
    customer_headers = auth_headers(
        client, "insight-shopper@example.com", "ShopperPass1!", role="customer"
    )

    fake_knot.pages = [
        {
            "merchant": {"id": 19, "name": "DoorDash"},
            "transactions": [
                {
                    "id": "txn-A",
                    "datetime": "2025-01-01T12:00:00+00:00",
                    "price": {"total": "12.50", "currency": "USD"},
                    "products": [],
                },
                {
                    "id": "txn-B",
                    "datetime": "2025-01-02T12:00:00+00:00",
                    "price": {"total": "7.25", "currency": "USD"},
                    "products": [],
                },
            ],
            "next_cursor": None,
        }
    ]
    res = client.post("/api/knot/sync", headers=customer_headers, json={"merchant_id": 19})
    assert res.status_code == 200

    res = client.get("/api/insights/spending", headers=customer_headers)
    assert res.status_code == 200, res.text
    insights = res.json()
    assert len(insights) == 1
    row = insights[0]
    assert row["merchant_name"] == "DoorDash"
    assert row["purchase_count"] == 2
    assert abs(row["total_spent"] - 19.75) < 0.001
