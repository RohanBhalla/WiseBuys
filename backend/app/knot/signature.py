from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Iterable


def _normalize_header_keys(headers: dict[str, str]) -> dict[str, str]:
    """Knot's signature spec uses canonical (Title-Case) names for the standard
    headers: Content-Length, Content-Type, Encryption-Type. ASGI lowercases
    headers, so we recover those names where possible."""

    canonical = {
        "content-length": "Content-Length",
        "content-type": "Content-Type",
        "encryption-type": "Encryption-Type",
    }
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        lower = key.lower()
        normalized[canonical.get(lower, key)] = value
    return normalized


def _build_signing_string(parts: dict[str, str], order: Iterable[str]) -> str:
    pieces: list[str] = []
    for key in order:
        if key in parts:
            pieces.append(key)
            pieces.append(parts[key])
    return "|".join(pieces)


def compute_knot_signature(
    secret: str,
    headers: dict[str, str],
    body_fields: dict[str, str],
) -> str:
    """Compute the HMAC-SHA256 signature per Knot's webhook spec.

    See https://docs.knotapi.com/webhooks#webhook-verification.
    """

    normalized_headers = _normalize_header_keys(headers)
    parts: dict[str, str] = {}
    for header in ("Content-Length", "Content-Type", "Encryption-Type"):
        if header in normalized_headers:
            parts[header] = str(normalized_headers[header])

    for key in ("event", "session_id"):
        if key in body_fields and body_fields[key] is not None:
            parts[key] = str(body_fields[key])

    order = ("Content-Length", "Content-Type", "Encryption-Type", "event", "session_id")
    signing_string = _build_signing_string(parts, order)
    digest = hmac.new(secret.encode("utf-8"), signing_string.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_knot_signature(
    provided_signature: str,
    secret: str,
    headers: dict[str, str],
    body_fields: dict[str, str],
) -> bool:
    expected = compute_knot_signature(secret, headers, body_fields)
    return hmac.compare_digest(expected, provided_signature)
