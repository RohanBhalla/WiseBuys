from sqlalchemy.orm import Session

from app.models import ValueTag

DEFAULT_TAGS: list[dict] = [
    {
        "slug": "sustainability",
        "label": "Sustainability",
        "description": "Operates with measurable environmental commitments.",
        "category": "environment",
    },
    {
        "slug": "ethically_sourced",
        "label": "Ethically Sourced",
        "description": "Materials sourced under fair labor and supply chain standards.",
        "category": "ethics",
    },
    {
        "slug": "black_owned",
        "label": "Black-Owned",
        "description": "Majority Black-owned and operated business.",
        "category": "ownership",
    },
    {
        "slug": "women_owned",
        "label": "Women-Owned",
        "description": "Majority women-owned and operated business.",
        "category": "ownership",
    },
    {
        "slug": "local",
        "label": "Local",
        "description": "Locally produced or operated within the customer's region.",
        "category": "sourcing",
    },
    {
        "slug": "b_corp",
        "label": "Certified B Corporation",
        "description": "Verified by B Lab as meeting social and environmental standards.",
        "category": "certification",
    },
    {
        "slug": "carbon_neutral",
        "label": "Carbon Neutral",
        "description": "Operations offset to achieve net-zero carbon emissions.",
        "category": "environment",
    },
    {
        "slug": "fair_trade",
        "label": "Fair Trade",
        "description": "Certified fair trade products.",
        "category": "certification",
    },
]


def seed_tags(db: Session) -> int:
    existing = {t.slug for t in db.query(ValueTag).all()}
    added = 0
    for spec in DEFAULT_TAGS:
        if spec["slug"] in existing:
            continue
        db.add(ValueTag(**spec))
        added += 1
    if added:
        db.commit()
    return added
