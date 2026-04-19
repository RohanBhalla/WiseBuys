"""Vendor-facing analytics: reach, competitors, pricing, top products, clicks.

Designed for demo / MVP scale: no precomputed pipeline. Reach numbers are
estimated by replaying the rules-only recommender across customers (capped),
and pricing/competitor metrics are aggregated directly from `vendor_products`.
"""

from __future__ import annotations

import logging
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    KnotPurchase,
    RecommendationClick,
    User,
    UserRole,
    VendorAllowedTag,
    VendorProduct,
    VendorProfile,
)
from app.services.recommendations import recommend_for_user_rules_only

logger = logging.getLogger(__name__)

# Cap how many customers we replay the recommender for, to keep this endpoint
# responsive on demo data. Tune up if you have a real workload.
REACH_SAMPLE_LIMIT = 200
REACH_RECS_PER_CUSTOMER = 8


@dataclass
class _CompetitorAccum:
    vendor_user_id: int
    company_legal_name: str
    shared_categories: set[str] = field(default_factory=set)
    shared_tag_labels: set[str] = field(default_factory=set)
    overlap_product_count: int = 0
    overlap_prices: list[float] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_price(p: VendorProduct) -> float | None:
    if p.price_hint is None:
        return None
    try:
        return float(p.price_hint)
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], target: float) -> float:
    """Return the percentile rank (0..100) of `target` in `values`.

    Uses the canonical "below + 0.5 * equal" definition so a value sitting at
    the median lands at 50.
    """

    if not values:
        return 0.0
    below = sum(1 for v in values if v < target)
    equal = sum(1 for v in values if v == target)
    return round((below + 0.5 * equal) / len(values) * 100.0, 1)


def _price_position_label(percentile: float) -> str:
    if percentile <= 25:
        return "value"
    if percentile <= 60:
        return "competitive"
    if percentile <= 85:
        return "premium"
    return "luxury"


def _pricing_recommendation(
    your_avg: float,
    market_median: float,
    market_min: float,
    market_max: float,
    percentile: float,
) -> str:
    if market_max == market_min or market_median == 0:
        return "Not enough competitor signal yet — keep an eye on this category as more vendors join."
    if percentile >= 80:
        gap = (your_avg / market_median - 1.0) * 100.0
        return (
            f"You're priced ~{gap:.0f}% above the category median. Lean into the differentiator copy "
            "and value tags so the premium reads as quality, not friction."
        )
    if percentile <= 25:
        gap = (1.0 - your_avg / market_median) * 100.0
        return (
            f"You're ~{gap:.0f}% below the category median — a clear value play. Consider a "
            "second tier or bundle to capture margin from price-insensitive shoppers."
        )
    return "Right in the sweet spot of the category. Compete on values, story, and reorder loyalty."


def compute_vendor_analytics(db: Session, vendor_user: User) -> dict:
    vendor_profile = (
        db.query(VendorProfile)
        .options(selectinload(VendorProfile.allowed_tags).selectinload(VendorAllowedTag.tag))
        .filter(VendorProfile.user_id == vendor_user.id)
        .one_or_none()
    )
    if vendor_profile is None:
        return _empty_payload(vendor_user)

    my_allowed_tag_ids = {link.tag_id for link in vendor_profile.allowed_tags if link.tag_id}
    my_allowed_tag_labels = {
        link.tag.label
        for link in vendor_profile.allowed_tags
        if getattr(link, "tag", None) and link.tag.label
    }

    my_products: list[VendorProduct] = (
        db.query(VendorProduct).filter(VendorProduct.vendor_user_id == vendor_user.id).all()
    )
    published_products = [p for p in my_products if p.is_published]

    my_categories_lower: set[str] = {
        p.category.strip().lower() for p in published_products if p.category
    }
    my_category_display: dict[str, str] = {}
    for p in published_products:
        if p.category:
            key = p.category.strip().lower()
            if key and key not in my_category_display:
                my_category_display[key] = p.category.strip()

    # ---- Click metrics ----------------------------------------------------
    cutoff_30d = _now() - timedelta(days=30)
    cutoff_7d = _now() - timedelta(days=7)
    total_clicks = (
        db.query(func.count(RecommendationClick.id))
        .filter(RecommendationClick.vendor_user_id == vendor_user.id)
        .scalar()
        or 0
    )
    clicks_30d = (
        db.query(func.count(RecommendationClick.id))
        .filter(
            RecommendationClick.vendor_user_id == vendor_user.id,
            RecommendationClick.created_at >= cutoff_30d,
        )
        .scalar()
        or 0
    )
    clicks_7d = (
        db.query(func.count(RecommendationClick.id))
        .filter(
            RecommendationClick.vendor_user_id == vendor_user.id,
            RecommendationClick.created_at >= cutoff_7d,
        )
        .scalar()
        or 0
    )
    clicks_by_product: dict[int, int] = {
        pid: count
        for pid, count in db.query(
            RecommendationClick.product_id, func.count(RecommendationClick.id)
        )
        .filter(RecommendationClick.vendor_user_id == vendor_user.id)
        .group_by(RecommendationClick.product_id)
        .all()
    }
    distinct_clickers = (
        db.query(func.count(func.distinct(RecommendationClick.user_id)))
        .filter(RecommendationClick.vendor_user_id == vendor_user.id)
        .scalar()
        or 0
    )

    # ---- Reach: replay rules-only recommender across active customers ----
    # The recommender is the source of truth: a customer can land on this
    # vendor's product via focus-tag overlap *or* purchase token/category
    # overlap, so we deliberately don't pre-filter by tag intersection.
    # Customers with zero profile and zero purchases can't get any recs, so we
    # skip them up-front to keep the loop tight.
    my_product_ids = {p.id for p in published_products}
    reach_customers: set[int] = set()
    appearances_per_product: Counter[int] = Counter()
    competitor_appearances: Counter[int] = Counter()  # vendor_user_id
    sample_size = 0

    if my_product_ids:
        users_with_purchases_select = select(KnotPurchase.user_id).distinct()
        candidate_customers = (
            db.query(User)
            .outerjoin(User.customer_profile)
            .filter(User.role == UserRole.customer, User.is_active.is_(True))
            .filter(
                # Either has a profile (focus-tag scoring possible) or has
                # synced purchases (token/category scoring possible).
                (User.customer_profile.has())
                | (User.id.in_(users_with_purchases_select))
            )
            .limit(REACH_SAMPLE_LIMIT)
            .all()
        )

        for customer in candidate_customers:
            sample_size += 1
            try:
                recs = recommend_for_user_rules_only(
                    db, customer, limit=REACH_RECS_PER_CUSTOMER
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reach replay failed for user_id=%s: %s", customer.id, exc)
                continue
            if not recs:
                continue
            owned_in_recs = [r for r in recs if r.product.id in my_product_ids]
            if owned_in_recs:
                reach_customers.add(customer.id)
                for r in owned_in_recs:
                    appearances_per_product[r.product.id] += 1
                for r in recs:
                    if r.product.vendor_user_id != vendor_user.id:
                        competitor_appearances[r.product.vendor_user_id] += 1

    total_customers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.customer, User.is_active.is_(True))
        .scalar()
        or 0
    )

    # ---- Competitors ------------------------------------------------------
    competitors_q = (
        db.query(VendorProduct, VendorProfile)
        .join(VendorProfile, VendorProfile.user_id == VendorProduct.vendor_user_id)
        .options(selectinload(VendorProfile.allowed_tags).selectinload(VendorAllowedTag.tag))
        .filter(VendorProduct.is_published.is_(True))
        .filter(VendorProduct.vendor_user_id != vendor_user.id)
    )
    if my_categories_lower:
        # Crude SQL prefilter using LIKE-equivalent: pull a manageable pool then filter in Python.
        competitors_q = competitors_q.limit(2000)
    competitor_rows = competitors_q.all() if my_categories_lower else []

    competitor_accum: dict[int, _CompetitorAccum] = {}
    for product, profile in competitor_rows:
        cat = (product.category or "").strip().lower()
        if cat not in my_categories_lower:
            continue
        acc = competitor_accum.get(profile.user_id)
        if acc is None:
            acc = _CompetitorAccum(
                vendor_user_id=profile.user_id,
                company_legal_name=profile.company_legal_name,
            )
            competitor_accum[profile.user_id] = acc
        if product.category:
            acc.shared_categories.add(product.category.strip())
        their_labels = {
            link.tag.label
            for link in profile.allowed_tags
            if getattr(link, "tag", None) and link.tag.label
        }
        acc.shared_tag_labels |= their_labels & my_allowed_tag_labels
        acc.overlap_product_count += 1
        price = _safe_price(product)
        if price is not None:
            acc.overlap_prices.append(price)

    competitors_payload = []
    your_avg_overall = _avg([_safe_price(p) for p in published_products])
    for acc in competitor_accum.values():
        their_avg = _avg(acc.overlap_prices) if acc.overlap_prices else None
        if their_avg is not None and your_avg_overall is not None and your_avg_overall > 0:
            position_pct = (your_avg_overall / their_avg - 1.0) * 100.0
            if position_pct >= 8:
                position = "you priced higher"
            elif position_pct <= -8:
                position = "you priced lower"
            else:
                position = "comparable pricing"
        else:
            position = "no price overlap yet"
        score = (
            len(acc.shared_categories) * 2
            + len(acc.shared_tag_labels)
            + min(acc.overlap_product_count, 10) * 0.5
            + competitor_appearances.get(acc.vendor_user_id, 0) * 0.25
        )
        competitors_payload.append(
            {
                "vendor_user_id": acc.vendor_user_id,
                "company_legal_name": acc.company_legal_name,
                "shared_categories": sorted(acc.shared_categories),
                "shared_tag_labels": sorted(acc.shared_tag_labels),
                "overlap_product_count": acc.overlap_product_count,
                "their_avg_price": round(their_avg, 2) if their_avg is not None else None,
                "your_avg_price": round(your_avg_overall, 2)
                if your_avg_overall is not None
                else None,
                "price_position": position,
                "co_recommendation_count": competitor_appearances.get(acc.vendor_user_id, 0),
                "overlap_score": round(score, 2),
            }
        )
    competitors_payload.sort(key=lambda c: c["overlap_score"], reverse=True)
    competitors_payload = competitors_payload[:8]

    # ---- Pricing insights -------------------------------------------------
    market_prices_by_category: dict[str, list[float]] = defaultdict(list)
    if my_categories_lower:
        all_market_q = (
            db.query(VendorProduct.category, VendorProduct.price_hint)
            .filter(VendorProduct.is_published.is_(True))
            .filter(VendorProduct.price_hint.isnot(None))
            .filter(VendorProduct.category.isnot(None))
        )
        for category, price in all_market_q.all():
            if not category:
                continue
            key = category.strip().lower()
            if key not in my_categories_lower:
                continue
            try:
                market_prices_by_category[key].append(float(price))
            except (TypeError, ValueError):
                continue

    your_prices_by_category: dict[str, list[float]] = defaultdict(list)
    for p in published_products:
        if not p.category:
            continue
        price = _safe_price(p)
        if price is None:
            continue
        your_prices_by_category[p.category.strip().lower()].append(price)

    pricing_payload = []
    for cat_key, your_prices in your_prices_by_category.items():
        market_prices = market_prices_by_category.get(cat_key, [])
        # Ensure the market reference includes my own prices so a single-vendor
        # category still gets a sensible (centered) percentile.
        reference_prices = market_prices or list(your_prices)
        your_avg = _avg(your_prices) or 0.0
        market_avg = _avg(reference_prices) or 0.0
        market_median = (
            statistics.median(reference_prices) if reference_prices else 0.0
        )
        market_min = min(reference_prices) if reference_prices else 0.0
        market_max = max(reference_prices) if reference_prices else 0.0
        percentile = _percentile(reference_prices, your_avg)
        position_label = _price_position_label(percentile)
        recommendation = _pricing_recommendation(
            your_avg, market_median or your_avg, market_min, market_max, percentile
        )
        pricing_payload.append(
            {
                "category": my_category_display.get(cat_key, cat_key),
                "your_avg_price": round(your_avg, 2),
                "your_min_price": round(min(your_prices), 2),
                "your_max_price": round(max(your_prices), 2),
                "market_avg_price": round(market_avg, 2),
                "market_median_price": round(market_median, 2),
                "market_min_price": round(market_min, 2),
                "market_max_price": round(market_max, 2),
                "market_sample_size": len(reference_prices),
                "percentile": percentile,
                "position": position_label,
                "recommendation": recommendation,
            }
        )
    pricing_payload.sort(key=lambda r: r["category"].lower())

    # ---- Top products -----------------------------------------------------
    by_id = {p.id: p for p in my_products}
    top_products_payload = []
    candidate_ids = set(appearances_per_product.keys()) | set(clicks_by_product.keys())
    for pid in candidate_ids:
        p = by_id.get(pid)
        if not p:
            continue
        top_products_payload.append(
            {
                "product_id": p.id,
                "name": p.name,
                "category": p.category,
                "price_hint": float(p.price_hint) if p.price_hint is not None else None,
                "is_published": p.is_published,
                "recommendation_appearances": appearances_per_product.get(p.id, 0),
                "click_count": clicks_by_product.get(p.id, 0),
            }
        )
    # Add unranked published products with zero appearances so the vendor sees
    # what's not landing yet.
    for p in published_products:
        if p.id in candidate_ids:
            continue
        top_products_payload.append(
            {
                "product_id": p.id,
                "name": p.name,
                "category": p.category,
                "price_hint": float(p.price_hint) if p.price_hint is not None else None,
                "is_published": p.is_published,
                "recommendation_appearances": 0,
                "click_count": 0,
            }
        )
    top_products_payload.sort(
        key=lambda r: (
            r["click_count"],
            r["recommendation_appearances"],
            r["price_hint"] or 0.0,
        ),
        reverse=True,
    )
    top_products_payload = top_products_payload[:10]

    # ---- Recent clicks ----------------------------------------------------
    recent_clicks_q = (
        db.query(RecommendationClick)
        .options(selectinload(RecommendationClick.product))
        .filter(RecommendationClick.vendor_user_id == vendor_user.id)
        .order_by(RecommendationClick.created_at.desc())
        .limit(8)
        .all()
    )
    recent_clicks = [
        {
            "id": c.id,
            "product_id": c.product_id,
            "product_name": c.product.name if c.product else None,
            "source": c.source,
            "created_at": c.created_at,
        }
        for c in recent_clicks_q
    ]

    return {
        "summary": {
            "vendor_user_id": vendor_user.id,
            "company_legal_name": vendor_profile.company_legal_name,
            "total_products": len(my_products),
            "published_products": len(published_products),
            "allowed_tag_count": len(my_allowed_tag_ids),
            "total_clicks": int(total_clicks),
            "clicks_last_30d": int(clicks_30d),
            "clicks_last_7d": int(clicks_7d),
            "distinct_click_users": int(distinct_clickers),
            "recommended_customers": len(reach_customers),
            "recommendation_appearances": int(sum(appearances_per_product.values())),
            "reach_sample_size": sample_size,
            "total_active_customers": int(total_customers),
        },
        "competitors": competitors_payload,
        "pricing_insights": pricing_payload,
        "top_products": top_products_payload,
        "recent_clicks": recent_clicks,
    }


def _empty_payload(vendor_user: User) -> dict:
    return {
        "summary": {
            "vendor_user_id": vendor_user.id,
            "company_legal_name": "",
            "total_products": 0,
            "published_products": 0,
            "allowed_tag_count": 0,
            "total_clicks": 0,
            "clicks_last_30d": 0,
            "clicks_last_7d": 0,
            "distinct_click_users": 0,
            "recommended_customers": 0,
            "recommendation_appearances": 0,
            "reach_sample_size": 0,
            "total_active_customers": 0,
        },
        "competitors": [],
        "pricing_insights": [],
        "top_products": [],
        "recent_clicks": [],
    }


def _avg(values: list[float | None] | list[float]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)
