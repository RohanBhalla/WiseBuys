"""Optional demo vendors + published catalog for Knot / recommendation QA.

Products use names and categories that overlap typical Transaction Link line
items (e.g. DoorDash → ``food-delivery``) and the rules engine in
``app.services.recommendations`` (token overlap ≥2, category match).

Enable with ``SEED_DEMO_VENDORS=true`` in ``.env``. Idempotent: skips if the
first demo vendor email already exists.
"""

from __future__ import annotations

from datetime import datetime, timezone

import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import db_is_postgresql
from app.models import (
    User,
    UserRole,
    ValueTag,
    VendorAllowedTag,
    VendorApplication,
    VendorApplicationStatus,
    VendorApplicationTag,
    VendorProduct,
    VendorProfile,
)

logger = logging.getLogger(__name__)

# Shared dev password for all demo vendor accounts (document in README only).
DEMO_VENDOR_PASSWORD_PLAIN = "WiseBuysDemoVendor1!"

DEMO_VENDORS: list[dict] = [
    {
        "email": "demo.v.greenbasket@wisebuys.example.com",
        "company_legal_name": "GreenBasket Foods Co.",
        "company_website": "https://greenbasket.demo.wisebuys.example.com",
        "tag_slugs": ["sustainability", "local"],
        "products": [
            {
                "name": "Organic Cold Brew Coffee Concentrate 32oz",
                "sku": "DEMO-GB-CB",
                "category": "food-delivery",
                "currency": "USD",
                "price_hint": 18.99,
                "differentiator": "Low-waste refill pouch; pairs with oat milk lattes from your delivery history.",
                "key_features": ["organic", "cold brew", "refill pouch"],
            },
            {
                "name": "Barista Oat Milk Half Gallon",
                "sku": "DEMO-GB-OAT",
                "category": "food-delivery",
                "currency": "USD",
                "price_hint": 6.49,
                "differentiator": "Creamy foam for cold brew and matcha drinks.",
                "key_features": ["oat milk", "barista", "dairy-free"],
            },
            {
                "name": "Local Farm Harvest Grain Bowl Kit",
                "sku": "DEMO-GB-BOWL",
                "category": "food-delivery",
                "currency": "USD",
                "price_hint": 12.5,
                "differentiator": "Swaps in for burrito bowls and salad orders.",
                "key_features": ["grain bowl", "local greens", "microwave"],
            },
        ],
    },
    {
        "email": "demo.v.rootsandmarrow@wisebuys.example.com",
        "company_legal_name": "Roots & Marrow Supply",
        "company_website": "https://rootsmarrow.demo.wisebuys.example.com",
        "tag_slugs": ["black_owned", "ethically_sourced"],
        "products": [
            {
                "name": "Bamboo Athletic Crew Socks 3-Pack",
                "sku": "DEMO-RM-SOCK",
                "category": "apparel",
                "currency": "USD",
                "price_hint": 24.0,
                "differentiator": "Same category signal as activewear in marketplace tests.",
                "key_features": ["bamboo", "athletic", "moisture-wicking"],
            },
            {
                "name": "Small Batch Jerky Sampler — Chicken & Beef",
                "sku": "DEMO-RM-JERKY",
                "category": "food-delivery",
                "currency": "USD",
                "price_hint": 16.0,
                "differentiator": "High-protein swap for chicken sandwich cravings.",
                "key_features": ["chicken", "beef", "high protein"],
            },
        ],
    },
    {
        "email": "demo.v.sunriseroasters@wisebuys.example.com",
        "company_legal_name": "Sunrise Roasters Collective",
        "company_website": "https://sunrise.demo.wisebuys.example.com",
        "tag_slugs": ["women_owned", "local"],
        "products": [
            {
                "name": "Small Batch Dark Roast Whole Bean Coffee 12oz",
                "sku": "DEMO-SR-BEAN",
                "category": "food-delivery",
                "currency": "USD",
                "price_hint": 17.5,
                "differentiator": "Roasted weekly; complements cold brew and latte line items.",
                "key_features": ["whole bean", "dark roast", "small batch"],
            },
            {
                "name": "Ceramic Travel Mug for Coffee 16oz",
                "sku": "DEMO-SR-MUG",
                "category": "everyday",
                "currency": "USD",
                "price_hint": 28.0,
                "differentiator": "Reusable cup for delivery coffee runs.",
                "key_features": ["ceramic", "travel mug", "coffee"],
            },
        ],
    },
    {
        "email": "demo.v.ethicalessentials@wisebuys.example.com",
        "company_legal_name": "Ethical Essentials Refill Co.",
        "company_website": "https://ethical.demo.wisebuys.example.com",
        "tag_slugs": ["fair_trade", "sustainability"],
        "products": [
            {
                "name": "Compostable Takeout Container Set 24ct",
                "sku": "DEMO-EE-BOX",
                "category": "food-delivery",
                "currency": "USD",
                "price_hint": 14.25,
                "differentiator": "Lower-impact alternative to plastic clamshells from delivery meals.",
                "key_features": ["compostable", "takeout", "containers"],
            },
            {
                "name": "Refill Dish Soap Concentrate Glass Bottle",
                "sku": "DEMO-EE-SOAP",
                "category": "everyday",
                "currency": "USD",
                "price_hint": 9.99,
                "differentiator": "Refill model for household cleaners after grocery-style orders.",
                "key_features": ["refill", "plant-based", "glass bottle"],
            },
        ],
    },
]


def _tag_ids_for_slugs(db: Session, slugs: list[str]) -> list[int]:
    tags = db.query(ValueTag).filter(ValueTag.slug.in_(slugs), ValueTag.is_active.is_(True)).all()
    by_slug = {t.slug: t.id for t in tags}
    missing = [s for s in slugs if s not in by_slug]
    if missing:
        raise RuntimeError(f"Demo vendor seed: missing tags: {missing}")
    return [by_slug[s] for s in slugs]


def _approve_application(
    db: Session,
    *,
    application: VendorApplication,
    admin: User,
    allowed_tag_ids: list[int],
) -> VendorProfile:
    applicant = db.get(User, application.applicant_user_id)
    if not applicant:
        raise RuntimeError("Demo vendor seed: applicant missing")
    applicant.role = UserRole.vendor

    profile = db.query(VendorProfile).filter(VendorProfile.user_id == applicant.id).one_or_none()
    if not profile:
        profile = VendorProfile(
            user_id=applicant.id,
            company_legal_name=application.company_legal_name,
            company_website=application.company_website,
            country=application.country,
            application_id=application.id,
        )
        db.add(profile)
        db.flush()
    else:
        profile.company_legal_name = application.company_legal_name
        profile.company_website = application.company_website
        profile.country = application.country
        profile.application_id = application.id

    db.query(VendorAllowedTag).filter(VendorAllowedTag.vendor_profile_id == profile.id).delete()
    db.flush()
    for tid in set(allowed_tag_ids):
        db.add(VendorAllowedTag(vendor_profile_id=profile.id, tag_id=tid))

    application.status = VendorApplicationStatus.approved
    application.reviewed_by_user_id = admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return profile


def seed_demo_vendors(db: Session) -> int:
    """Create approved demo vendors + published products. Returns rows created (vendors)."""

    settings = get_settings()
    if not settings.seed_demo_vendors:
        return 0

    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if not admin:
        return 0

    sentinel = DEMO_VENDORS[0]["email"]
    if db.query(User).filter(User.email == sentinel).one_or_none():
        return 0

    from app.security import hash_password

    created = 0
    for spec in DEMO_VENDORS:
        tag_ids = _tag_ids_for_slugs(db, spec["tag_slugs"])
        user = User(
            email=spec["email"],
            password_hash=hash_password(DEMO_VENDOR_PASSWORD_PLAIN),
            role=UserRole.vendor,
            is_active=True,
        )
        db.add(user)
        db.flush()

        application = VendorApplication(
            applicant_user_id=user.id,
            company_legal_name=spec["company_legal_name"],
            company_website=spec["company_website"],
            contact_email=spec["email"],
            country="US",
            narrative="Seeded demo vendor for WiseBuys + Knot recommendation QA.",
            evidence_urls=["https://wisebuys.example.com/demo-vendor-proof"],
            status=VendorApplicationStatus.submitted,
        )
        db.add(application)
        db.flush()
        for tid in tag_ids:
            db.add(VendorApplicationTag(application_id=application.id, tag_id=tid))
        db.flush()

        _approve_application(db, application=application, admin=admin, allowed_tag_ids=tag_ids)

        for p in spec["products"]:
            db.add(
                VendorProduct(
                    vendor_user_id=user.id,
                    name=p["name"],
                    sku=p.get("sku"),
                    category=p.get("category"),
                    currency=p.get("currency", "USD"),
                    price_hint=p.get("price_hint"),
                    differentiator=p.get("differentiator"),
                    key_features=p.get("key_features"),
                    is_published=True,
                )
            )
        db.flush()
        created += 1

    db.commit()

    if db_is_postgresql(db):
        try:
            from app.services.vector_index import upsert_product_embedding

            for row in db.query(VendorProduct.id).filter(VendorProduct.sku.like("DEMO-%")).all():
                upsert_product_embedding(db, row[0])
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Demo vendor product embeddings skipped: %s", exc)
            db.rollback()

    return created
