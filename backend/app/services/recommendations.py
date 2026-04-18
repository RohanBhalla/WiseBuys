from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy.orm import Session, selectinload

from app.models import (
    CustomerProfile,
    KnotLineItem,
    KnotPurchase,
    User,
    VendorAllowedTag,
    VendorProduct,
    VendorProfile,
)

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "of",
    "a",
    "an",
    "to",
    "in",
    "on",
    "by",
    "or",
    "from",
    "pack",
    "ct",
    "count",
    "size",
    "set",
    "kit",
    "box",
    "case",
    "oz",
    "lb",
    "ml",
    "fl",
    "x",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")

PRIMARY_WEIGHT = 3.0
SECONDARY_WEIGHT = 1.0
TOKEN_OVERLAP_WEIGHT = 0.5
CATEGORY_MATCH_WEIGHT = 1.5
EVIDENCE_LIMIT = 3


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2}


def _category_for_purchase(purchase: KnotPurchase) -> str | None:
    """Very light heuristic: bucket merchants/products into a coarse category
    so we can weight category-aligned vendor products higher.
    """

    name = (purchase.merchant_name or "").lower()
    if any(k in name for k in ("doordash", "ubereats", "uber eats", "grubhub")):
        return "food-delivery"
    if "amazon" in name or "walmart" in name or "target" in name:
        return "everyday"
    if any(k in name for k in ("sephora", "ulta")):
        return "beauty"
    if any(k in name for k in ("nike", "adidas", "lululemon")):
        return "apparel"
    return None


@dataclass
class Recommendation:
    product: VendorProduct
    score: float
    reasons: list[str] = field(default_factory=list)
    evidence_line_item_ids: list[int] = field(default_factory=list)


def _focus_tag_ids(profile: CustomerProfile | None) -> tuple[int | None, set[int]]:
    if not profile:
        return None, set()
    primary_id = profile.primary_focus_tag_id
    secondary = {link.tag_id for link in profile.secondary_focuses if link.tag_id}
    return primary_id, secondary


def _allowed_tag_ids(vendor: VendorProfile | None) -> set[int]:
    if not vendor:
        return set()
    return {link.tag_id for link in vendor.allowed_tags if link.tag_id}


def recommend_for_user(
    db: Session,
    user: User,
    *,
    limit: int = 10,
    line_item_limit: int = 200,
) -> list[Recommendation]:
    profile = (
        db.query(CustomerProfile)
        .options(selectinload(CustomerProfile.secondary_focuses))
        .filter(CustomerProfile.user_id == user.id)
        .one_or_none()
    )
    primary_tag_id, secondary_tag_ids = _focus_tag_ids(profile)

    purchases = (
        db.query(KnotPurchase)
        .options(selectinload(KnotPurchase.line_items))
        .filter(KnotPurchase.user_id == user.id)
        .order_by(KnotPurchase.occurred_at.desc().nullslast())
        .limit(50)
        .all()
    )

    line_items: list[tuple[KnotPurchase, KnotLineItem]] = []
    for p in purchases:
        for li in p.line_items:
            line_items.append((p, li))
            if len(line_items) >= line_item_limit:
                break
        if len(line_items) >= line_item_limit:
            break

    line_item_tokens: list[tuple[int, str | None, set[str]]] = [
        (li.id, _category_for_purchase(p), _tokenize(li.name)) for p, li in line_items
    ]

    category_counts: Counter[str] = Counter(
        cat for _, cat, _ in line_item_tokens if cat
    )
    dominant_categories = {cat for cat, _ in category_counts.most_common(3)}

    products = (
        db.query(VendorProduct)
        .filter(VendorProduct.is_published.is_(True))
        .all()
    )

    vendor_user_ids = {p.vendor_user_id for p in products}
    vendor_profiles_by_user = {}
    if vendor_user_ids:
        vendor_profiles_by_user = {
            vp.user_id: vp
            for vp in db.query(VendorProfile)
            .options(selectinload(VendorProfile.allowed_tags).selectinload(VendorAllowedTag.tag))
            .filter(VendorProfile.user_id.in_(vendor_user_ids))
            .all()
        }

    recs: list[Recommendation] = []
    for product in products:
        vendor = vendor_profiles_by_user.get(product.vendor_user_id)
        if vendor is None:
            continue
        allowed = _allowed_tag_ids(vendor)
        score = 0.0
        reasons: list[str] = []

        if primary_tag_id and primary_tag_id in allowed:
            score += PRIMARY_WEIGHT
            primary_label = next(
                (link.tag.label for link in vendor.allowed_tags if link.tag_id == primary_tag_id),
                None,
            )
            reasons.append(
                f"Matches your primary focus{f' ({primary_label})' if primary_label else ''}"
            )

        secondary_overlap = secondary_tag_ids & allowed
        if secondary_overlap:
            score += SECONDARY_WEIGHT * len(secondary_overlap)
            reasons.append(f"Aligned with {len(secondary_overlap)} of your other focuses")

        product_tokens = _tokenize(product.name) | _tokenize(product.category)
        evidence_ids: list[int] = []
        token_hits = 0
        for li_id, _cat, li_tokens in line_item_tokens:
            overlap = product_tokens & li_tokens
            if len(overlap) >= 2:
                token_hits += len(overlap)
                if len(evidence_ids) < EVIDENCE_LIMIT:
                    evidence_ids.append(li_id)
        if token_hits:
            score += TOKEN_OVERLAP_WEIGHT * token_hits
            reasons.append("Similar to items you've recently bought")

        if product.category and dominant_categories:
            product_cat = product.category.lower().replace(" ", "-")
            if product_cat in dominant_categories or any(
                cat in product_cat for cat in dominant_categories
            ):
                score += CATEGORY_MATCH_WEIGHT
                reasons.append("Common category in your purchase history")

        if score <= 0:
            continue

        recs.append(
            Recommendation(
                product=product,
                score=round(score, 2),
                reasons=reasons,
                evidence_line_item_ids=evidence_ids,
            )
        )

    recs.sort(key=lambda r: r.score, reverse=True)
    return recs[:limit]


def spending_insights(db: Session, user: User) -> list[dict]:
    """Aggregate spending per merchant from `knot_purchases`."""

    rows = (
        db.query(KnotPurchase)
        .filter(KnotPurchase.user_id == user.id)
        .all()
    )
    by_merchant: dict[int, dict] = {}
    for p in rows:
        if p.knot_merchant_id is None:
            continue
        bucket = by_merchant.setdefault(
            p.knot_merchant_id,
            {
                "knot_merchant_id": p.knot_merchant_id,
                "merchant_name": p.merchant_name,
                "currency": p.currency,
                "purchase_count": 0,
                "total_spent": 0.0,
            },
        )
        bucket["purchase_count"] += 1
        if p.total is not None:
            bucket["total_spent"] = float(bucket["total_spent"]) + float(p.total)
        if not bucket["merchant_name"] and p.merchant_name:
            bucket["merchant_name"] = p.merchant_name
        if not bucket["currency"] and p.currency:
            bucket["currency"] = p.currency

    out = list(by_merchant.values())
    out.sort(key=lambda b: b["total_spent"], reverse=True)
    return out


def explain_score(items: Iterable[Recommendation]) -> list[dict]:
    return [
        {
            "product_id": r.product.id,
            "score": r.score,
            "reasons": r.reasons,
        }
        for r in items
    ]
