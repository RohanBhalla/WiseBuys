from __future__ import annotations

from typing import Any


class FakeKnotClient:
    """Test double that mimics the subset of `KnotClient` used by routers
    and the sync service. Behavior is configurable via instance attributes."""

    def __init__(
        self,
        *,
        session_id: str = "fake-session-123",
        merchant: dict | None = None,
        pages: list[dict] | None = None,
    ) -> None:
        self.session_id = session_id
        self.merchant = merchant or {"id": 19, "name": "DoorDash"}
        self.pages = pages if pages is not None else []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def create_session(
        self,
        external_user_id: str,
        session_type: str = "transaction_link",
        metadata: dict | None = None,
    ) -> dict:
        self.calls.append(
            ("create_session", {"external_user_id": external_user_id, "type": session_type, "metadata": metadata})
        )
        return {"session": self.session_id}

    def sync_transactions(
        self,
        external_user_id: str,
        merchant_id: int,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        self.calls.append(
            (
                "sync_transactions",
                {
                    "external_user_id": external_user_id,
                    "merchant_id": merchant_id,
                    "cursor": cursor,
                    "limit": limit,
                },
            )
        )
        if not self.pages:
            return {
                "merchant": self.merchant,
                "transactions": [],
                "next_cursor": None,
                "limit": limit,
            }
        page = self.pages.pop(0)
        return {
            "merchant": page.get("merchant", self.merchant),
            "transactions": page.get("transactions", []),
            "next_cursor": page.get("next_cursor"),
            "limit": limit,
        }

    def get_transaction(self, transaction_id: str) -> dict:
        return {"id": transaction_id}

    def list_merchants(self, type_: str = "transaction_link") -> dict:
        return {"merchants": [self.merchant]}

    def link_account_dev(self, *_, **__) -> dict:
        return {"linked": True}

    def close(self) -> None:
        return None


def sample_transactions(start_id: int = 1, count: int = 2) -> list[dict]:
    """Build a small batch of Knot-shaped transactions for tests."""

    out: list[dict] = []
    for i in range(start_id, start_id + count):
        out.append(
            {
                "id": f"txn-{i:04d}",
                "external_id": f"ext-{i:04d}",
                "datetime": f"2025-01-0{(i % 9) + 1}T12:00:00+00:00",
                "url": f"https://example.com/orders/{i}",
                "order_status": "DELIVERED",
                "payment_methods": [
                    {"type": "CARD", "brand": "VISA", "last_four": "1111", "transaction_amount": "10.00"}
                ],
                "price": {
                    "sub_total": "10.00",
                    "adjustments": [],
                    "total": "11.00",
                    "currency": "USD",
                },
                "products": [
                    {
                        "external_id": f"prod-{i}-a",
                        "name": f"Item {i}A",
                        "description": "Demo item",
                        "url": f"https://example.com/items/{i}/a",
                        "image_url": None,
                        "quantity": 1,
                        "price": {"sub_total": "5.00", "total": "5.00", "unit_price": "5.00"},
                        "seller": {"name": "Demo Seller", "url": None},
                        "eligibility": [],
                    },
                    {
                        "external_id": f"prod-{i}-b",
                        "name": f"Item {i}B",
                        "description": None,
                        "url": None,
                        "image_url": None,
                        "quantity": 2,
                        "price": {"sub_total": "5.00", "total": "5.00", "unit_price": "2.50"},
                        "seller": None,
                        "eligibility": [],
                    },
                ],
            }
        )
    return out
