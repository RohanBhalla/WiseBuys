from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import exists
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import db_is_postgresql
from app.models import (
    CustomerProfile,
    CustomerSecondaryFocus,
    KnotLineItem,
    KnotPurchase,
    User,
    VendorAllowedTag,
    VendorProduct,
    VendorProductTag,
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
# Per-product tag bonuses sit slightly above the vendor-level allow-list signal
# because the vendor explicitly stamped this product with the tag.
PRODUCT_TAG_PRIMARY_WEIGHT = 1.5
PRODUCT_TAG_SECONDARY_WEIGHT = 0.6
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


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _recency_factor(occurred_at: datetime | None) -> float:
    if occurred_at is None:
        return 0.0
    now = datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - occurred_at).total_seconds() / 86400.0)
    if days <= 7:
        return 1.0
    if days >= 120:
        return 0.0
    return max(0.0, 1.0 - (days - 7.0) / (120.0 - 7.0))


@dataclass
class ComparablePurchase:
    line_item_id: int | None = None
    name: str = ""
    merchant_name: str | None = None
    unit_price: float | None = None
    total: float | None = None
    currency: str | None = None
    occurred_at: datetime | None = None


@dataclass
class Recommendation:
    product: VendorProduct
    score: float
    reasons: list[str] = field(default_factory=list)
    evidence_line_item_ids: list[int] = field(default_factory=list)
    comparable: ComparablePurchase | None = None
    insight: str = ""


def _focus_tag_ids(profile: CustomerProfile | None) -> tuple[int | None, set[int]]:
    if not profile:
        return None, set()
    primary_id = profile.primary_focus_tag_id
    secondary = {link.tag_id for link in profile.secondary_focuses if link.tag_id}
    return primary_id, secondary


def _focus_labels(profile: CustomerProfile | None) -> tuple[str | None, list[str]]:
    """Return (primary_label, secondary_labels) using eager-loaded tags."""

    if not profile:
        return None, []
    primary_label = (
        profile.primary_focus.label
        if getattr(profile, "primary_focus", None) and profile.primary_focus
        else None
    )
    secondary_labels: list[str] = []
    for link in profile.secondary_focuses:
        tag = getattr(link, "tag", None)
        if tag and tag.label and tag.label != primary_label:
            secondary_labels.append(tag.label)
    return primary_label, secondary_labels


def _allowed_tag_ids(vendor: VendorProfile | None) -> set[int]:
    if not vendor:
        return set()
    return {link.tag_id for link in vendor.allowed_tags if link.tag_id}


def _allowed_labels_by_id(vendor: VendorProfile | None) -> dict[int, str]:
    if not vendor:
        return {}
    out: dict[int, str] = {}
    for link in vendor.allowed_tags:
        tag = getattr(link, "tag", None)
        if tag and tag.label:
            out[link.tag_id] = tag.label
    return out


def _product_tag_ids(product: VendorProduct) -> set[int]:
    return {link.tag_id for link in getattr(product, "tag_links", []) or [] if link.tag_id}


def _product_tag_labels_by_id(product: VendorProduct) -> dict[int, str]:
    out: dict[int, str] = {}
    for link in getattr(product, "tag_links", []) or []:
        tag = getattr(link, "tag", None)
        if tag and tag.label:
            out[link.tag_id] = tag.label
    return out


def _format_money(value: float | None, currency: str | None) -> str | None:
    if value is None:
        return None
    code = (currency or "USD").upper()
    if code == "USD":
        return f"${float(value):,.2f}"
    return f"{float(value):,.2f} {code}"


def _humanize_list(items: list[str]) -> str:
    items = [s for s in items if s]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _pick_comparable(
    product: VendorProduct,
    line_items_full: list[tuple[KnotPurchase, KnotLineItem]],
    product_tokens: set[str],
    dominant_categories: set[str],
) -> ComparablePurchase | None:
    """Pick the most relevant past line item to compare against this product."""

    if not line_items_full:
        return None
    product_cat = (product.category or "").lower().replace(" ", "-") if product.category else ""

    best: tuple[float, KnotPurchase, KnotLineItem] | None = None
    for purchase, li in line_items_full:
        li_tokens = _tokenize(li.name)
        overlap = len(product_tokens & li_tokens)
        cat = _category_for_purchase(purchase) or ""
        cat_match = 1.0 if cat and (cat == product_cat or cat in dominant_categories) else 0.0
        recency = _recency_factor(purchase.occurred_at)
        score = overlap * 2.0 + cat_match * 1.0 + recency * 0.5
        if score < 1.5:
            continue
        if best is None or score > best[0]:
            best = (score, purchase, li)

    if best is None:
        return None
    _, purchase, li = best
    unit_price = float(li.unit_price) if li.unit_price is not None else None
    total = float(li.total) if li.total is not None else None
    if unit_price is None and total is not None and (li.quantity or 1) > 0:
        unit_price = total / float(li.quantity or 1)
    return ComparablePurchase(
        line_item_id=li.id,
        name=li.name,
        merchant_name=purchase.merchant_name,
        unit_price=unit_price,
        total=total,
        currency=purchase.currency,
        occurred_at=purchase.occurred_at,
    )


def _build_insight(
    product: VendorProduct,
    comparable: ComparablePurchase | None,
    *,
    primary_label: str | None,
    secondary_labels: list[str],
    matched_vendor_labels: list[str],
    matched_product_labels: list[str] | None = None,
    vec_sim: float | None = None,
    token_hits: int = 0,
) -> str:
    """Construct a textual insight that explains why the alternative is better.

    Considers tags, product features, and price (cheaper = great deal,
    more expensive = justified by features/values, similar = even swap).
    """

    sentences: list[str] = []
    alt_price = float(product.price_hint) if product.price_hint is not None else None
    alt_str = _format_money(alt_price, product.currency)

    differentiator = (product.differentiator or "").strip().rstrip(".")
    feature_list = list(product.key_features or [])[:3]
    feature_brief = differentiator or (", ".join(feature_list) if feature_list else "")

    # 1) Frame: "Instead of X from Y at $Z, try ..." or generic
    if comparable:
        comp_price = comparable.unit_price if comparable.unit_price is not None else comparable.total
        comp_str = _format_money(comp_price, comparable.currency or product.currency)
        merch = f" from {comparable.merchant_name}" if comparable.merchant_name else ""
        if alt_str and comp_str:
            sentences.append(
                f"Instead of {comparable.name}{merch} at {comp_str}, try {product.name} at {alt_str}."
            )
        elif alt_str:
            sentences.append(
                f"A values-aligned swap for your past {comparable.name}{merch}: {product.name} at {alt_str}."
            )
        else:
            sentences.append(
                f"A values-aligned swap for your past {comparable.name}{merch}: {product.name}."
            )
    else:
        opener = f"{product.name} ({alt_str})" if alt_str else product.name
        sentences.append(f"{opener} lines up with the way you already shop.")

    # 2) Price framing — only when we have both numbers to compare
    if comparable and alt_price is not None:
        comp_price_val = (
            comparable.unit_price if comparable.unit_price is not None else comparable.total
        )
        if comp_price_val is not None and float(comp_price_val) > 0:
            diff = alt_price - float(comp_price_val)
            pct = diff / float(comp_price_val) * 100.0
            abs_diff_str = _format_money(abs(diff), product.currency)
            if diff <= -0.5:
                sentences.append(
                    f"That's about {abs_diff_str} less (~{abs(pct):.0f}% cheaper) — a clear deal for the same job."
                )
            elif diff >= 0.5 and pct >= 8:
                if feature_brief:
                    sentences.append(
                        f"It runs {abs_diff_str} more (~{pct:.0f}% premium), and that uplift buys you {feature_brief.lower()}."
                    )
                else:
                    sentences.append(
                        f"It runs {abs_diff_str} more (~{pct:.0f}% premium), but the supply chain and quality back the price."
                    )
            else:
                if feature_brief:
                    sentences.append(
                        f"Priced about the same, so you trade up to {feature_brief.lower()} at no real cost."
                    )
                else:
                    sentences.append(
                        "Priced about the same, so the swap costs you nothing — only the values gap closes."
                    )

    # 3) Value alignment — first to user's profile focuses, then vendor stamps
    aligned = []
    if primary_label:
        aligned.append(primary_label)
    aligned.extend(l for l in secondary_labels if l != primary_label)
    aligned = aligned[:3]

    product_matched = [l for l in (matched_product_labels or []) if l]
    matched = [l for l in matched_vendor_labels if l]

    if product_matched:
        # Per-product stamps trump vendor-wide allow-lists in the narrative.
        sentences.append(
            f"This specific product is stamped for {_humanize_list(product_matched[:3])}, the values you flagged on your profile."
        )
    elif aligned and matched:
        overlap_first = [l for l in aligned if l in matched]
        rest = [l for l in aligned if l not in matched]
        ordered = overlap_first + rest
        sentences.append(
            f"It also matches your focus on {_humanize_list(ordered[:3])} — the values you flagged on your profile."
        )
    elif aligned:
        sentences.append(
            f"It also leans into your focus on {_humanize_list(aligned)}."
        )
    elif matched:
        sentences.append(
            f"The vendor is verified on {_humanize_list(matched[:2])}, expanding your purchases into more conscious territory."
        )

    # 4) Trailing: highlight features when no price comparison happened
    if not comparable and feature_brief:
        sentences.append(f"Standout traits: {feature_brief}.")

    # 5) Optional semantic confidence note when no token-level overlap surfaced
    if vec_sim is not None and token_hits == 0 and vec_sim >= 0.45:
        sentences.append(
            "Pulled in because it semantically resembles your recent purchases and stated values."
        )

    return " ".join(sentences).strip()


def recommend_for_user_rules_only(
    db: Session,
    user: User,
    *,
    limit: int = 10,
    line_item_limit: int = 200,
    exclude_product_ids: set[int] | None = None,
) -> list[Recommendation]:
    profile = (
        db.query(CustomerProfile)
        .options(
            selectinload(CustomerProfile.primary_focus),
            selectinload(CustomerProfile.secondary_focuses).selectinload(CustomerSecondaryFocus.tag),
        )
        .filter(CustomerProfile.user_id == user.id)
        .one_or_none()
    )
    primary_tag_id, secondary_tag_ids = _focus_tag_ids(profile)
    primary_label, secondary_labels = _focus_labels(profile)

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

    category_counts: Counter[str] = Counter(cat for _, cat, _ in line_item_tokens if cat)
    dominant_categories = {cat for cat, _ in category_counts.most_common(3)}

    products = (
        db.query(VendorProduct)
        .options(selectinload(VendorProduct.tag_links).selectinload(VendorProductTag.tag))
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

    exclude = exclude_product_ids or set()
    recs: list[Recommendation] = []
    for product in products:
        if product.id in exclude:
            continue
        vendor = vendor_profiles_by_user.get(product.vendor_user_id)
        if vendor is None:
            continue
        allowed = _allowed_tag_ids(vendor)
        allowed_label_by_id = _allowed_labels_by_id(vendor)
        score = 0.0
        reasons: list[str] = []
        matched_vendor_labels: list[str] = []

        if primary_tag_id and primary_tag_id in allowed:
            score += PRIMARY_WEIGHT
            v_primary_label = allowed_label_by_id.get(primary_tag_id)
            if v_primary_label:
                matched_vendor_labels.append(v_primary_label)
            reasons.append(
                f"Matches your primary focus{f' ({v_primary_label})' if v_primary_label else ''}"
            )

        secondary_overlap = secondary_tag_ids & allowed
        if secondary_overlap:
            score += SECONDARY_WEIGHT * len(secondary_overlap)
            reasons.append(f"Aligned with {len(secondary_overlap)} of your other focuses")
            for tid in secondary_overlap:
                lbl = allowed_label_by_id.get(tid)
                if lbl and lbl not in matched_vendor_labels:
                    matched_vendor_labels.append(lbl)

        product_tag_ids = _product_tag_ids(product)
        product_tag_labels = _product_tag_labels_by_id(product)
        matched_product_labels: list[str] = []
        if primary_tag_id and primary_tag_id in product_tag_ids:
            score += PRODUCT_TAG_PRIMARY_WEIGHT
            lbl = product_tag_labels.get(primary_tag_id)
            if lbl:
                matched_product_labels.append(lbl)
            reasons.append(
                f"Tagged for your primary focus{f' ({lbl})' if lbl else ''}"
            )
        product_secondary_overlap = secondary_tag_ids & product_tag_ids
        if product_secondary_overlap:
            score += PRODUCT_TAG_SECONDARY_WEIGHT * len(product_secondary_overlap)
            reasons.append(
                f"Tagged for {len(product_secondary_overlap)} of your other focuses"
            )
            for tid in product_secondary_overlap:
                lbl = product_tag_labels.get(tid)
                if lbl and lbl not in matched_product_labels:
                    matched_product_labels.append(lbl)

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
            if product_cat in dominant_categories or any(cat in product_cat for cat in dominant_categories):
                score += CATEGORY_MATCH_WEIGHT
                reasons.append("Common category in your purchase history")

        if score <= 0:
            continue

        comparable = _pick_comparable(product, line_items, product_tokens, dominant_categories)
        insight = _build_insight(
            product,
            comparable,
            primary_label=primary_label,
            secondary_labels=secondary_labels,
            matched_vendor_labels=matched_vendor_labels,
            matched_product_labels=matched_product_labels,
            vec_sim=None,
            token_hits=token_hits,
        )

        recs.append(
            Recommendation(
                product=product,
                score=round(score, 2),
                reasons=reasons,
                evidence_line_item_ids=evidence_ids,
                comparable=comparable,
                insight=insight,
            )
        )

    recs.sort(key=lambda r: r.score, reverse=True)
    return recs[:limit]


def recommend_for_user_hybrid(
    db: Session,
    user: User,
    *,
    limit: int = 10,
    line_item_limit: int = 200,
) -> list[Recommendation]:
    """Vector + tag pre-filter + weighted re-rank.

    - Postgres: uses pgvector cosine_distance for ANN ordering.
    - SQLite: loads candidates and sorts by cosine in Python (no ANN).
    """
    settings = get_settings()
    profile = (
        db.query(CustomerProfile)
        .options(
            selectinload(CustomerProfile.primary_focus),
            selectinload(CustomerProfile.secondary_focuses).selectinload(CustomerSecondaryFocus.tag),
        )
        .filter(CustomerProfile.user_id == user.id)
        .one_or_none()
    )
    if not profile or profile.embedding is None:
        return []

    customer_vec = profile.embedding
    primary_tag_id, secondary_tag_ids = _focus_tag_ids(profile)
    primary_label, secondary_labels = _focus_labels(profile)
    focus_union: set[int] = set()
    if primary_tag_id:
        focus_union.add(primary_tag_id)
    focus_union |= secondary_tag_ids

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
    li_occurred: dict[int, datetime | None] = {li.id: p.occurred_at for p, li in line_items}

    category_counts: Counter[str] = Counter(cat for _, cat, _ in line_item_tokens if cat)
    dominant_categories = {cat for cat, _ in category_counts.most_common(3)}

    q = (
        db.query(VendorProduct, VendorProfile)
        .join(VendorProfile, VendorProfile.user_id == VendorProduct.vendor_user_id)
        .options(
            selectinload(VendorProfile.allowed_tags).selectinload(VendorAllowedTag.tag),
            selectinload(VendorProduct.tag_links).selectinload(VendorProductTag.tag),
        )
        .filter(VendorProduct.is_published.is_(True))
        .filter(VendorProduct.embedding.isnot(None))
    )
    if focus_union:
        q = q.filter(
            exists().where(
                VendorAllowedTag.vendor_profile_id == VendorProfile.id,
                VendorAllowedTag.tag_id.in_(focus_union),
            )
        )

    pool = max(limit, settings.vector_candidate_pool)
    if db_is_postgresql(db):
        rows = q.order_by(VendorProduct.embedding.cosine_distance(customer_vec)).limit(pool).all()
    else:
        # SQLite fallback: no SQL cosine_distance. Load a bounded pool and sort in Python.
        rows = q.limit(max(pool, 250)).all()
        rows.sort(
            key=lambda row: _dot(customer_vec, row[0].embedding) if row[0].embedding is not None else 0.0,
            reverse=True,
        )
        rows = rows[:pool]

    scored: list[tuple[float, Recommendation]] = []
    for product, vendor in rows:
        if product.embedding is None:
            continue
        vec_sim = max(0.0, min(1.0, _dot(customer_vec, product.embedding)))
        allowed = _allowed_tag_ids(vendor)
        allowed_label_by_id = _allowed_labels_by_id(vendor)
        reasons: list[str] = []
        matched_vendor_labels: list[str] = []
        score = settings.vector_rec_weight_vec * vec_sim

        if vec_sim >= 0.22:
            reasons.append("Semantically similar to your purchase history and values")

        if primary_tag_id and primary_tag_id in allowed:
            score += settings.vector_rec_weight_primary
            v_primary_label = allowed_label_by_id.get(primary_tag_id)
            if v_primary_label:
                matched_vendor_labels.append(v_primary_label)
            reasons.append(
                f"Matches your primary focus{f' ({v_primary_label})' if v_primary_label else ''}"
            )

        secondary_overlap = secondary_tag_ids & allowed
        if secondary_overlap:
            score += settings.vector_rec_weight_secondary * len(secondary_overlap)
            reasons.append(f"Aligned with {len(secondary_overlap)} of your other focuses")
            for tid in secondary_overlap:
                lbl = allowed_label_by_id.get(tid)
                if lbl and lbl not in matched_vendor_labels:
                    matched_vendor_labels.append(lbl)

        product_tag_ids = _product_tag_ids(product)
        product_tag_labels = _product_tag_labels_by_id(product)
        matched_product_labels: list[str] = []
        if primary_tag_id and primary_tag_id in product_tag_ids:
            score += PRODUCT_TAG_PRIMARY_WEIGHT
            lbl = product_tag_labels.get(primary_tag_id)
            if lbl:
                matched_product_labels.append(lbl)
            reasons.append(
                f"Tagged for your primary focus{f' ({lbl})' if lbl else ''}"
            )
        product_secondary_overlap = secondary_tag_ids & product_tag_ids
        if product_secondary_overlap:
            score += PRODUCT_TAG_SECONDARY_WEIGHT * len(product_secondary_overlap)
            reasons.append(
                f"Tagged for {len(product_secondary_overlap)} of your other focuses"
            )
            for tid in product_secondary_overlap:
                lbl = product_tag_labels.get(tid)
                if lbl and lbl not in matched_product_labels:
                    matched_product_labels.append(lbl)

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
            score += settings.vector_rec_weight_token_overlap * token_hits
            reasons.append("Similar to items you've recently bought")

        if product.category and dominant_categories:
            product_cat = product.category.lower().replace(" ", "-")
            if product_cat in dominant_categories or any(cat in product_cat for cat in dominant_categories):
                score += settings.vector_rec_weight_category
                reasons.append("Common category in your purchase history")

        rec_vals = [_recency_factor(li_occurred.get(eid)) for eid in evidence_ids]
        recency_boost = max(rec_vals) if rec_vals else 0.0
        if recency_boost > 0:
            score += settings.vector_rec_weight_recency * recency_boost

        if not evidence_ids and vec_sim >= 0.35 and line_item_tokens:
            evidence_ids.append(line_item_tokens[0][0])

        if score <= 0:
            continue

        comparable = _pick_comparable(product, line_items, product_tokens, dominant_categories)
        insight = _build_insight(
            product,
            comparable,
            primary_label=primary_label,
            secondary_labels=secondary_labels,
            matched_vendor_labels=matched_vendor_labels,
            matched_product_labels=matched_product_labels,
            vec_sim=vec_sim,
            token_hits=token_hits,
        )

        scored.append(
            (
                score,
                Recommendation(
                    product=product,
                    score=round(score, 2),
                    reasons=reasons,
                    evidence_line_item_ids=evidence_ids,
                    comparable=comparable,
                    insight=insight,
                ),
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]


def recommend_for_user(
    db: Session,
    user: User,
    *,
    limit: int = 10,
    line_item_limit: int = 200,
) -> list[Recommendation]:
    settings = get_settings()
    hybrid: list[Recommendation] = []
    can_hybrid = (
        settings.vector_recs_enabled
        and bool(settings.gemini_api_key and str(settings.gemini_api_key).strip())
    )
    if can_hybrid:
        profile = (
            db.query(CustomerProfile)
            .filter(CustomerProfile.user_id == user.id)
            .one_or_none()
        )
        if profile and profile.embedding is not None:
            hybrid = recommend_for_user_hybrid(db, user, limit=limit, line_item_limit=line_item_limit)

    if hybrid:
        if len(hybrid) >= limit:
            return hybrid[:limit]
        seen = {r.product.id for r in hybrid}
        rules = recommend_for_user_rules_only(
            db,
            user,
            limit=limit * 2,
            line_item_limit=line_item_limit,
            exclude_product_ids=seen,
        )
        out = list(hybrid)
        for r in rules:
            if r.product.id in seen:
                continue
            out.append(r)
            seen.add(r.product.id)
            if len(out) >= limit:
                break
        return out[:limit]

    return recommend_for_user_rules_only(db, user, limit=limit, line_item_limit=line_item_limit)


def spending_insights(db: Session, user: User) -> list[dict]:
    """Aggregate spending per merchant from `knot_purchases`."""

    rows = db.query(KnotPurchase).filter(KnotPurchase.user_id == user.id).all()
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
