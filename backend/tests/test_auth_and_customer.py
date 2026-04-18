from tests.conftest import auth_headers


def test_customer_registration_creates_profile(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "shopper@example.com", "password": "ShopperPass1!", "role": "customer"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["role"] == "customer"
    token = body["access_token"]

    me = client.get("/api/customers/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    profile = me.json()
    assert profile["primary_focus"] is None
    assert profile["secondary_focuses"] == []


def test_customer_can_set_focuses_and_rewards(client):
    headers = auth_headers(client, "shopper2@example.com", "ShopperPass1!", role="customer")

    tags = client.get("/api/tags").json()
    sustainability = next(t for t in tags if t["slug"] == "sustainability")
    fair_trade = next(t for t in tags if t["slug"] == "fair_trade")
    local = next(t for t in tags if t["slug"] == "local")

    res = client.patch(
        "/api/customers/me",
        headers=headers,
        json={
            "primary_focus_tag_id": sustainability["id"],
            "secondary_focus_tag_ids": [fair_trade["id"], local["id"]],
            "rewards_preferences": {"mode": "points", "tiers_interest": True},
        },
    )
    assert res.status_code == 200, res.text
    profile = res.json()
    assert profile["primary_focus"]["slug"] == "sustainability"
    slugs = sorted(t["slug"] for t in profile["secondary_focuses"])
    assert slugs == ["fair_trade", "local"]
    assert profile["rewards_preferences"]["mode"] == "points"


def test_admin_cannot_self_register(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "evil@example.com", "password": "EvilPass1!", "role": "admin"},
    )
    assert res.status_code == 400


def test_invalid_tag_id_rejected(client):
    headers = auth_headers(client, "shopper3@example.com", "ShopperPass1!", role="customer")
    res = client.patch(
        "/api/customers/me",
        headers=headers,
        json={"primary_focus_tag_id": 99999},
    )
    assert res.status_code == 400
