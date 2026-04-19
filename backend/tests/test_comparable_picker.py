"""Unit tests for the comparable-purchase picker.

These tests pin down the quality bar that drives the dashboard "You bought"
panel: we should never anchor a recommendation on an obviously-unrelated past
purchase (e.g. a face cleanser as the comparable for a jerky sampler).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import KnotLineItem, KnotPurchase, VendorProduct
from app.services import recommendations as rec


def _purchase(merchant: str, name: str, *, days_ago: int, embedding=None) -> tuple[KnotPurchase, KnotLineItem]:
    occurred = datetime.now(timezone.utc) - timedelta(days=days_ago)
    p = KnotPurchase(
        id=days_ago + 1,
        user_id=1,
        knot_transaction_id=f"txn-{merchant}-{name}",
        knot_merchant_id=1,
        merchant_name=merchant,
        occurred_at=occurred,
        currency="USD",
    )
    li = KnotLineItem(
        id=days_ago + 100,
        purchase_id=p.id,
        name=name,
        unit_price=10.0,
        total=10.0,
        embedding=list(embedding) if embedding is not None else None,
    )
    return p, li


def _product(name: str, category: str | None, embedding=None) -> VendorProduct:
    p = VendorProduct(
        id=1,
        vendor_user_id=1,
        name=name,
        category=category,
        currency="USD",
        price_hint=12.0,
    )
    if embedding is not None:
        p.embedding = list(embedding)
    return p


def test_picker_returns_none_when_nothing_aligns():
    """Without semantic match AND without category/lexical overlap we MUST
    return None — the old behavior of grabbing the most recent purchase
    surfaced misleading pairings (cleanser shown as comparable for jerky)."""

    product = _product("Small Batch Jerky Sampler", category="food-delivery")
    line_items = [
        _purchase("Sephora", "Milky Jelly Cleanser", days_ago=1),
        _purchase("Lululemon", "Athletic Hoodie", days_ago=3),
    ]
    out = rec._pick_comparable(
        product,
        line_items,
        product_tokens=rec._tokenize(product.name),
        dominant_categories={"beauty", "apparel"},
    )
    assert out is None


def test_picker_uses_lexical_overlap_when_available():
    product = _product("Bamboo Athletic Crew Socks", category="apparel")
    line_items = [
        _purchase("Sephora", "Milky Jelly Cleanser", days_ago=1),
        _purchase("DICK'S", "Men's Athletic Crew Socks", days_ago=10),
    ]
    out = rec._pick_comparable(
        product,
        line_items,
        product_tokens=rec._tokenize(product.name),
        dominant_categories={"apparel"},
    )
    assert out is not None
    assert "Crew Socks" in out.name


def test_picker_requires_product_specific_category_match():
    """Category fallback should require the line item's coarse category to
    match the *product's* category, not just any dominant category."""

    product = _product("Compostable Takeout Container Set", category="food-delivery")
    # No food-delivery purchases at all — only Amazon (everyday) and Sephora.
    line_items = [
        _purchase("Amazon", "USB-C Cable", days_ago=2),
        _purchase("Sephora", "Milky Jelly Cleanser", days_ago=4),
    ]
    out = rec._pick_comparable(
        product,
        line_items,
        product_tokens=rec._tokenize(product.name),
        dominant_categories={"everyday", "beauty"},
    )
    assert out is None


def test_picker_prefers_semantic_match_when_embeddings_present():
    """When both product and line items have embeddings, cosine similarity
    should drive the choice — and the unrelated item must be rejected by the
    floor even if it scores higher lexically by accident."""

    # Construct unit vectors by index so cosine sim is predictable.
    def _onehot(slot: int, dim: int = 8) -> list[float]:
        v = [0.0] * dim
        v[slot] = 1.0
        return v

    product = _product("Bamboo Athletic Crew Socks", category="apparel", embedding=_onehot(0))
    socks = _purchase("DICK'S", "Athletic Socks", days_ago=10, embedding=_onehot(0))  # cos=1.0
    cleanser = _purchase("Sephora", "Milky Jelly Cleanser", days_ago=1, embedding=_onehot(3))  # cos=0.0

    out = rec._pick_comparable(
        product,
        [cleanser, socks],
        product_tokens=rec._tokenize(product.name),
        dominant_categories={"apparel", "beauty"},
    )
    assert out is not None
    assert "Athletic Socks" in out.name


def test_picker_floor_rejects_unrelated_semantic_neighbor():
    """If the only embedded line item is below the cosine floor, return None
    rather than surfacing a misleading neighbor."""

    def _onehot(slot: int, dim: int = 8) -> list[float]:
        v = [0.0] * dim
        v[slot] = 1.0
        return v

    product = _product("Bamboo Athletic Crew Socks", category="apparel", embedding=_onehot(0))
    cleanser = _purchase("Sephora", "Milky Jelly Cleanser", days_ago=1, embedding=_onehot(3))  # cos=0

    out = rec._pick_comparable(
        product,
        [cleanser],
        product_tokens=rec._tokenize(product.name),
        dominant_categories={"beauty"},
    )
    assert out is None


def test_picker_recency_breaks_ties_among_semantic_neighbors():
    def _vec(a: float, b: float) -> list[float]:
        # tiny 2-d unit-ish vector (we only care about ordering).
        import math
        norm = math.sqrt(a * a + b * b) or 1.0
        return [a / norm, b / norm]

    product = _product("Bamboo Athletic Crew Socks", category="apparel", embedding=_vec(0.9, 0.1))
    older = _purchase("DICK'S", "Athletic Socks", days_ago=60, embedding=_vec(0.95, 0.0))
    newer = _purchase("DICK'S", "Athletic Socks", days_ago=2, embedding=_vec(0.95, 0.0))

    out = rec._pick_comparable(
        product,
        [older, newer],
        product_tokens=rec._tokenize(product.name),
        dominant_categories={"apparel"},
    )
    assert out is not None
    # Same name + same merchant; recency tiebreak should pick the newer one.
    assert out.line_item_id == newer[1].id
