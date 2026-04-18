from fastapi import HTTPException, status

from app.knot.client import KnotClient, get_knot_client


def get_knot() -> KnotClient:
    """FastAPI dependency wrapper around the configured Knot client.

    Tests override this via `app.dependency_overrides[get_knot] = ...`.
    """

    try:
        return get_knot_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
