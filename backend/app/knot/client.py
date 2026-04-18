from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

DEV_BASE_URL = "https://development.knotapi.com"
PROD_BASE_URL = "https://production.knotapi.com"


class KnotError(Exception):
    def __init__(self, status_code: int, payload: Any):
        super().__init__(f"Knot API error {status_code}: {payload}")
        self.status_code = status_code
        self.payload = payload


class KnotClient:
    """Thin wrapper for the subset of Knot APIs WiseBuys uses."""

    def __init__(
        self,
        client_id: str,
        secret: str,
        environment: str = "development",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.client_id = client_id
        self.secret = secret
        self.environment = environment
        self.base_url = DEV_BASE_URL if environment != "production" else PROD_BASE_URL
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            auth=(client_id, secret),
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def _post(self, path: str, json: dict | None = None) -> dict:
        res = self._client.post(path, json=json or {})
        if res.status_code >= 400:
            try:
                payload = res.json()
            except ValueError:
                payload = res.text
            raise KnotError(res.status_code, payload)
        return res.json() if res.text else {}

    def _get(self, path: str, params: dict | None = None) -> dict:
        res = self._client.get(path, params=params)
        if res.status_code >= 400:
            try:
                payload = res.json()
            except ValueError:
                payload = res.text
            raise KnotError(res.status_code, payload)
        return res.json() if res.text else {}

    def create_session(
        self,
        external_user_id: str,
        session_type: str = "transaction_link",
        metadata: dict | None = None,
    ) -> dict:
        body: dict[str, Any] = {"type": session_type, "external_user_id": external_user_id}
        if metadata:
            body["metadata"] = metadata
        return self._post("/session/create", body)

    def sync_transactions(
        self,
        external_user_id: str,
        merchant_id: int,
        cursor: str | None = None,
        limit: int = 100,
    ) -> dict:
        body: dict[str, Any] = {
            "external_user_id": external_user_id,
            "merchant_id": merchant_id,
            "limit": limit,
        }
        if cursor:
            body["cursor"] = cursor
        return self._post("/transactions/sync", body)

    def get_transaction(self, transaction_id: str) -> dict:
        return self._get(f"/transactions/{transaction_id}")

    def list_merchants(self, type_: str = "transaction_link") -> dict:
        """List merchants for a product type.

        Knot exposes **POST /merchant/list** (not GET /merchants). We pass
        ``platform: "web"`` so the Web SDK merchant set matches this list.
        """

        body = {"type": type_, "platform": "web"}
        res = self._client.post("/merchant/list", json=body)
        if res.status_code >= 400:
            try:
                payload = res.json()
            except ValueError:
                payload = res.text
            raise KnotError(res.status_code, payload)
        parsed: Any = res.json() if res.text else []
        rows: list[Any]
        if isinstance(parsed, list):
            rows = parsed
        elif isinstance(parsed, dict):
            inner = parsed.get("merchants") or parsed.get("data")
            rows = inner if isinstance(inner, list) else []
        else:
            rows = []
        return {"merchants": rows}

    def link_account_dev(
        self,
        external_user_id: str,
        merchant_id: int,
        product_type: str = "transaction_link",
    ) -> dict:
        """Development-only: bypass the SDK and link a test account."""
        return self._post(
            "/link/account",
            {
                "external_user_id": external_user_id,
                "merchant_id": merchant_id,
                "type": product_type,
            },
        )

    def close(self) -> None:
        self._client.close()


def get_knot_client() -> KnotClient:
    settings = get_settings()
    if not settings.knot_client_id or not settings.knot_secret:
        raise RuntimeError(
            "Knot is not configured. Set KNOT_CLIENT_ID and KNOT_SECRET in your .env."
        )
    return KnotClient(
        client_id=settings.knot_client_id,
        secret=settings.knot_secret,
        environment=settings.knot_environment,
    )
