from tests.conftest import auth_headers


def _admin_headers(client):
    return auth_headers(client, "admin@wisebuys.example.com", "AdminPass123!")


def _seed_vendor_and_apply(client, email="vendor@example.com"):
    headers = auth_headers(client, email, "VendorPass1!", role="vendor")
    tags = client.get("/api/tags").json()
    requested = [
        next(t for t in tags if t["slug"] == "sustainability")["id"],
        next(t for t in tags if t["slug"] == "ethically_sourced")["id"],
        next(t for t in tags if t["slug"] == "black_owned")["id"],
    ]

    res = client.post(
        "/api/vendors/applications",
        headers=headers,
        json={
            "company_legal_name": "Good Goods LLC",
            "company_website": "https://goodgoods.example",
            "contact_email": email,
            "country": "US",
            "narrative": "We make sustainably sourced household products.",
            "requested_tag_ids": requested,
            "evidence_urls": ["https://goodgoods.example/about", "https://goodgoods.example/cert.pdf"],
        },
    )
    assert res.status_code == 201, res.text
    return headers, res.json(), requested


def test_full_vendor_lifecycle(client):
    vendor_headers, application, requested = _seed_vendor_and_apply(client)
    assert application["status"] == "submitted"

    catalog_blocked = client.get("/api/catalog/products", headers=vendor_headers)
    assert catalog_blocked.status_code == 403

    admin_headers = _admin_headers(client)
    listing = client.get("/api/admin/applications", headers=admin_headers)
    assert listing.status_code == 200
    assert any(a["id"] == application["id"] for a in listing.json())

    needs_info = client.post(
        f"/api/admin/applications/{application['id']}/decision",
        headers=admin_headers,
        json={"status": "needs_info", "admin_notes": "Please share supplier docs."},
    )
    assert needs_info.status_code == 200
    assert needs_info.json()["status"] == "needs_info"

    approve = client.post(
        f"/api/admin/applications/{application['id']}/decision",
        headers=admin_headers,
        json={
            "status": "approved",
            "admin_notes": "Verified.",
            "allowed_tag_ids": requested[:2],
        },
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    profile = client.get("/api/vendors/me", headers=vendor_headers)
    assert profile.status_code == 200
    body = profile.json()
    allowed_slugs = sorted(t["slug"] for t in body["allowed_tags"])
    assert allowed_slugs == ["ethically_sourced", "sustainability"]

    create = client.post(
        "/api/catalog/products",
        headers=vendor_headers,
        json={
            "name": "Recycled Canvas Tote",
            "sku": "GG-TOTE-01",
            "category": "bags",
            "currency": "USD",
            "price_hint": "24.99",
            "differentiator": "Made from 100% recycled ocean plastics.",
            "key_features": ["recycled materials", "reinforced stitching", "lifetime warranty"],
            "is_published": True,
        },
    )
    assert create.status_code == 201, create.text
    product = create.json()
    assert product["name"] == "Recycled Canvas Tote"

    update = client.patch(
        f"/api/catalog/products/{product['id']}",
        headers=vendor_headers,
        json={"price_hint": "22.00", "key_features": ["recycled materials", "machine washable"]},
    )
    assert update.status_code == 200
    assert update.json()["price_hint"] == "22.00"

    listing = client.get("/api/catalog/products", headers=vendor_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_approval_requires_allowed_tag_ids(client):
    vendor_headers, application, _ = _seed_vendor_and_apply(client, email="vendor2@example.com")
    admin_headers = _admin_headers(client)

    bad = client.post(
        f"/api/admin/applications/{application['id']}/decision",
        headers=admin_headers,
        json={"status": "approved"},
    )
    assert bad.status_code == 400


def test_open_application_blocks_duplicate_submission(client):
    vendor_headers, application, _ = _seed_vendor_and_apply(client, email="vendor3@example.com")

    dup = client.post(
        "/api/vendors/applications",
        headers=vendor_headers,
        json={
            "company_legal_name": "Other Co",
            "contact_email": "vendor3@example.com",
            "requested_tag_ids": [],
        },
    )
    assert dup.status_code == 409
