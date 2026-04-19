"""Build embedding text, signatures, and upsert vectors for hybrid recommendations."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import (
    CustomerProfile,
    CustomerSecondaryFocus,
    KnotLineItem,
    KnotPurchase,
    VendorProduct,
    VendorProductTag,
    VendorProfile,
)
from app.models.vendor import VendorAllowedTag
from app.services import embeddings as embeddings_service

logger = logging.getLogger(__name__)


def signature_for_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _coarse_category_for_merchant(purchase: KnotPurchase) -> str | None:
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


def build_product_text(product: VendorProduct, vendor: VendorProfile | None) -> str:
    parts: list[str] = [f"Product name: {product.name}"]
    if product.category:
        parts.append(f"Category: {product.category}")
    if product.differentiator:
        parts.append(f"Differentiator: {product.differentiator}")
    if product.key_features:
        feats = product.key_features
        if isinstance(feats, list) and feats:
            joined = ", ".join(str(f) for f in feats[:16])
            parts.append(f"Key features: {joined}")

    # Per-product tags get top billing in the embedding text because they're
    # the vendor's claim about THIS specific product.
    product_tag_labels: list[str] = []
    for link in getattr(product, "tag_links", []) or []:
        tag = getattr(link, "tag", None)
        if tag and tag.label:
            product_tag_labels.append(tag.label)
    if product_tag_labels:
        parts.append("Product value tags: " + ", ".join(sorted(set(product_tag_labels))))

    if vendor and vendor.allowed_tags:
        labels: list[str] = []
        for link in vendor.allowed_tags:
            if link.tag and link.tag.label:
                labels.append(link.tag.label)
        # Avoid duplicating product tags already captured above.
        labels = [l for l in labels if l not in set(product_tag_labels)]
        if labels:
            parts.append("Vendor allowed tags: " + ", ".join(sorted(set(labels))))
    return "\n".join(parts)


def build_customer_text(
    profile: CustomerProfile,
    *,
    line_item_snippets: list[str],
    dominant_categories: list[str],
) -> str:
    parts: list[str] = []
    if profile.primary_focus and profile.primary_focus.label:
        tag = profile.primary_focus
        parts.append(f"Primary values focus: {tag.label}")
        if tag.description:
            parts.append(f"Primary focus description: {tag.description.strip()}")
    sec_labels: list[str] = []
    for link in profile.secondary_focuses or []:
        if link.tag and link.tag.label:
            sec_labels.append(link.tag.label)
    if sec_labels:
        parts.append("Secondary values focuses: " + ", ".join(sorted(set(sec_labels))))
    if dominant_categories:
        parts.append("Purchase history categories: " + ", ".join(dominant_categories))
    if line_item_snippets:
        joined = "; ".join(line_item_snippets[:48])
        parts.append(f"Recent purchase line items: {joined}")
    return "\n".join(parts) if parts else "Values-focused shopper"


def upsert_product_embedding(db: Session, product_id: int) -> bool:
    """Compute and store product embedding if enabled and content changed."""
    if not get_settings().vector_recs_enabled:
        return False
    product = (
        db.query(VendorProduct)
        .options(selectinload(VendorProduct.tag_links).selectinload(VendorProductTag.tag))
        .filter(VendorProduct.id == product_id)
        .one_or_none()
    )
    if not product:
        return False
    vendor = (
        db.query(VendorProfile)
        .options(selectinload(VendorProfile.allowed_tags).selectinload(VendorAllowedTag.tag))
        .filter(VendorProfile.user_id == product.vendor_user_id)
        .one_or_none()
    )
    text = build_product_text(product, vendor)
    sig = signature_for_text(text)
    if product.embedding_signature == sig and product.embedding is not None:
        return True
    vectors = embeddings_service.embed_documents([text])
    if vectors is None:
        logger.warning("Product %s embedding skipped (embed_documents returned None)", product_id)
        return False
    product.embedding = vectors[0]
    product.embedding_signature = sig
    product.embedded_at = datetime.now(timezone.utc)
    db.add(product)
    return True


def upsert_customer_embedding(db: Session, user_id: int) -> bool:
    """Compute and store customer profile embedding if enabled and content changed."""
    if not get_settings().vector_recs_enabled:
        return False
    profile = (
        db.query(CustomerProfile)
        .options(
            selectinload(CustomerProfile.primary_focus),
            selectinload(CustomerProfile.secondary_focuses).selectinload(CustomerSecondaryFocus.tag),
        )
        .filter(CustomerProfile.user_id == user_id)
        .one_or_none()
    )
    if not profile:
        return False

    purchases = (
        db.query(KnotPurchase)
        .options(selectinload(KnotPurchase.line_items))
        .filter(KnotPurchase.user_id == user_id)
        .order_by(KnotPurchase.occurred_at.desc().nullslast())
        .limit(50)
        .all()
    )
    line_items: list[tuple[KnotPurchase, KnotLineItem]] = []
    for p in purchases:
        for li in p.line_items:
            line_items.append((p, li))
            if len(line_items) >= 200:
                break
        if len(line_items) >= 200:
            break

    category_counts: Counter[str] = Counter()
    snippets: list[str] = []
    for p, li in line_items:
        cat = _coarse_category_for_merchant(p)
        if cat:
            category_counts[cat] += 1
        name = (li.name or "").strip()
        desc = (li.description or "").strip()
        if name:
            piece = name[:120]
            if desc:
                piece = f"{piece} — {desc[:120]}"
            snippets.append(piece)

    dominant = [c for c, _ in category_counts.most_common(3)]
    text = build_customer_text(profile, line_item_snippets=snippets, dominant_categories=dominant)
    sig = signature_for_text(text)
    if profile.embedding_signature == sig and profile.embedding is not None:
        return True
    vec = embeddings_service.embed_query(text)
    if vec is None:
        logger.warning("Customer %s embedding skipped (embed_query returned None)", user_id)
        return False
    profile.embedding = vec
    profile.embedding_signature = sig
    profile.embedded_at = datetime.now(timezone.utc)
    db.add(profile)
    return True


def backfill_all_embeddings(db: Session) -> dict[str, int]:
    """Idempotent backfill for published products and all customer profiles."""
    if not get_settings().vector_recs_enabled:
        return {"products": 0, "customers": 0}
    p_ok = 0
    for row in db.query(VendorProduct.id).filter(VendorProduct.is_published.is_(True)).all():
        if upsert_product_embedding(db, row[0]):
            p_ok += 1
        db.commit()
    c_ok = 0
    for row in db.query(CustomerProfile.user_id).all():
        if upsert_customer_embedding(db, row[0]):
            c_ok += 1
        db.commit()
    return {"products": p_ok, "customers": c_ok}
