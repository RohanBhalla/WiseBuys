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


def build_product_text(
    product: VendorProduct, vendor: VendorProfile | None
) -> tuple[str, str]:
    """Return ``(title, body)`` for the product embedding.

    Best practices for product retrieval embeddings (Google's RETRIEVAL_DOCUMENT
    docs + standard IR guidance):
      - Use the product **name** as the document ``title`` so it's weighted
        more heavily by the model.
      - Keep the body about THIS product. We deliberately drop the vendor's
        global allowed-tag list because it's the same for every product from
        that vendor and otherwise pulls every sibling product towards the same
        embedding cluster, killing discrimination at retrieval time.
    """
    title = (product.name or "").strip() or "Product"
    parts: list[str] = []
    if product.category:
        parts.append(f"Category: {product.category}")
    if product.differentiator:
        parts.append(f"Differentiator: {product.differentiator}")
    if product.key_features:
        feats = product.key_features
        if isinstance(feats, list) and feats:
            joined = ", ".join(str(f) for f in feats[:16])
            parts.append(f"Key features: {joined}")

    product_tag_labels: list[str] = []
    for link in getattr(product, "tag_links", []) or []:
        tag = getattr(link, "tag", None)
        if tag and tag.label:
            product_tag_labels.append(tag.label)
    if product_tag_labels:
        parts.append("Value tags: " + ", ".join(sorted(set(product_tag_labels))))
    elif vendor and vendor.allowed_tags:
        # Fallback only when the product has no per-product tags: surface the
        # vendor's allowed tags as a softer signal so we still capture the
        # vendor's positioning. We cap the list short to limit dilution.
        labels: list[str] = []
        for link in vendor.allowed_tags:
            if link.tag and link.tag.label:
                labels.append(link.tag.label)
        if labels:
            parts.append(
                "Vendor positioning: " + ", ".join(sorted(set(labels))[:5])
            )

    body = "\n".join(parts) if parts else title
    return title, body


def build_customer_text(
    profile: CustomerProfile,
    *,
    line_item_snippets: list[str],
    dominant_categories: list[str],
) -> str:
    """Build the customer-side query text.

    We deliberately keep this short (focuses + dominant categories + a small,
    deduped sample of recent items). Dumping dozens of line items into a query
    embedding flattens the signal toward the average, which hurts retrieval
    precision (e.g. a beauty buyer with one Big Mac purchase shouldn't look
    like a food-delivery shopper). We let per-line-item embeddings carry the
    item-level signal instead — used downstream for the comparable picker.
    """
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
        # Cap aggressively (was 48). Items are already deduped + recency-sorted
        # by the caller.
        joined = "; ".join(line_item_snippets[:12])
        parts.append(f"Recent items: {joined}")
    return "\n".join(parts) if parts else "Values-focused shopper"


def build_line_item_text(
    line_item: KnotLineItem, purchase: KnotPurchase
) -> tuple[str, str]:
    """Build ``(title, body)`` for a line item document embedding.

    Title is the line-item name (the strongest signal for product semantics).
    Body adds merchant context, an optional description, and the coarse
    merchant category — all of which help disambiguate generic names like
    "Crew Socks" or "Big Mac Meal".
    """
    title = (line_item.name or "").strip() or "Item"
    parts: list[str] = []
    if purchase.merchant_name:
        parts.append(f"Merchant: {purchase.merchant_name}")
    cat = _coarse_category_for_merchant(purchase)
    if cat:
        parts.append(f"Coarse category: {cat}")
    desc = (line_item.description or "").strip()
    if desc:
        parts.append(f"Description: {desc[:240]}")
    body = "\n".join(parts) if parts else title
    return title, body


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
    title, body = build_product_text(product, vendor)
    sig = signature_for_text(f"{title}\n---\n{body}")
    if product.embedding_signature == sig and product.embedding is not None:
        return True
    vectors = embeddings_service.embed_documents_with_titles([(title, body)])
    if vectors is None:
        logger.warning("Product %s embedding skipped (embed_documents returned None)", product_id)
        return False
    product.embedding = vectors[0]
    product.embedding_signature = sig
    product.embedded_at = datetime.now(timezone.utc)
    db.add(product)
    return True


def upsert_line_item_embeddings(
    db: Session, user_id: int, *, line_item_limit: int = 200
) -> int:
    """Embed (or refresh) recent line items for a user.

    Returns the number of embeddings written. Idempotent via signature: only
    items whose ``(title, body)`` content changed are re-encoded. Bounded by
    ``line_item_limit`` so a long-tail user with thousands of past items still
    only embeds the recent slice that drives recommendations.
    """
    if not get_settings().vector_recs_enabled:
        return 0

    # Pull recent purchases, then their line items, in recency order.
    purchases = (
        db.query(KnotPurchase)
        .options(selectinload(KnotPurchase.line_items))
        .filter(KnotPurchase.user_id == user_id)
        .order_by(KnotPurchase.occurred_at.desc().nullslast())
        .limit(50)
        .all()
    )

    pending: list[tuple[int, str, str]] = []  # (li_id, title, body)
    for p in purchases:
        for li in p.line_items:
            if len(pending) >= line_item_limit:
                break
            title, body = build_line_item_text(li, p)
            sig = signature_for_text(f"{title}\n---\n{body}")
            if li.embedding_signature == sig and li.embedding is not None:
                continue
            pending.append((li.id, title, body))
            li.embedding_signature = sig  # provisionally; only commit on success
        if len(pending) >= line_item_limit:
            break

    if not pending:
        return 0

    items_for_api = [(title, body) for _, title, body in pending]
    vectors = embeddings_service.embed_documents_with_titles(items_for_api)
    if vectors is None:
        # Roll back the provisional signatures so we retry next time.
        for li_id, _, _ in pending:
            db.query(KnotLineItem).filter(KnotLineItem.id == li_id).update(
                {"embedding_signature": None}
            )
        logger.warning(
            "Line-item embedding skipped for user=%s (embed_documents returned None)",
            user_id,
        )
        return 0

    now = datetime.now(timezone.utc)
    written = 0
    for (li_id, _, _), vec in zip(pending, vectors, strict=True):
        li = db.query(KnotLineItem).filter(KnotLineItem.id == li_id).one_or_none()
        if not li:
            continue
        li.embedding = vec
        li.embedded_at = now
        db.add(li)
        written += 1
    return written


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
    seen_keys: set[str] = set()
    for p, li in line_items:  # already recency-sorted via purchases query
        cat = _coarse_category_for_merchant(p)
        if cat:
            category_counts[cat] += 1
        name = (li.name or "").strip()
        if not name:
            continue
        # Dedupe by name + merchant so a customer who orders the same Big Mac
        # 12 times doesn't drown out a single Sephora purchase in the embedding.
        key = f"{name.lower()}::{(p.merchant_name or '').lower()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merch = f" @ {p.merchant_name}" if p.merchant_name else ""
        snippets.append(f"{name[:90]}{merch}")
        if len(snippets) >= 24:  # hard cap before downstream truncation
            break

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
    """Idempotent backfill for published products, customer profiles, and
    recent line items for every customer with synced purchases."""
    if not get_settings().vector_recs_enabled:
        return {"products": 0, "customers": 0, "line_items": 0}
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
    li_ok = 0
    user_ids = {row[0] for row in db.query(KnotPurchase.user_id).distinct().all()}
    for uid in user_ids:
        li_ok += upsert_line_item_embeddings(db, uid)
        db.commit()
    return {"products": p_ok, "customers": c_ok, "line_items": li_ok}
