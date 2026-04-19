import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_vendor, get_db

logger = logging.getLogger(__name__)
from app.models import (
    User,
    VendorProduct,
    VendorProductTag,
    VendorProfile,
)
from app.schemas.catalog import VendorProductCreate, VendorProductPublic, VendorProductUpdate

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _ensure_approved_vendor(db: Session, user: User) -> VendorProfile:
    profile = (
        db.query(VendorProfile)
        .options(selectinload(VendorProfile.allowed_tags))
        .filter(VendorProfile.user_id == user.id)
        .one_or_none()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vendor must be approved before managing catalog.",
        )
    return profile


def _validate_product_tag_ids(profile: VendorProfile, tag_ids: list[int]) -> set[int]:
    """Ensure every requested tag is in the vendor's approved allow-list."""

    if not tag_ids:
        return set()
    requested = set(int(tid) for tid in tag_ids)
    allowed = {link.tag_id for link in profile.allowed_tags if link.tag_id}
    missing = requested - allowed
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Tag ids {sorted(missing)} are not in your approved allow-list. "
                "Ask an admin to expand your allowed tags first."
            ),
        )
    return requested


def _sync_product_tags(db: Session, product: VendorProduct, tag_ids: set[int]) -> None:
    """Replace this product's tag links so they match `tag_ids` exactly."""

    existing_links = list(product.tag_links)
    existing_ids = {link.tag_id for link in existing_links}
    to_add = tag_ids - existing_ids
    to_remove = [link for link in existing_links if link.tag_id not in tag_ids]

    for link in to_remove:
        db.delete(link)
    for tid in to_add:
        db.add(VendorProductTag(product_id=product.id, tag_id=tid))


def _load_product_with_tags(db: Session, product_id: int) -> VendorProduct | None:
    return (
        db.query(VendorProduct)
        .options(selectinload(VendorProduct.tag_links).selectinload(VendorProductTag.tag))
        .filter(VendorProduct.id == product_id)
        .one_or_none()
    )


@router.get("/products", response_model=list[VendorProductPublic])
def list_my_products(
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> list[VendorProduct]:
    _ensure_approved_vendor(db, user)
    return (
        db.query(VendorProduct)
        .options(selectinload(VendorProduct.tag_links).selectinload(VendorProductTag.tag))
        .filter(VendorProduct.vendor_user_id == user.id)
        .order_by(VendorProduct.created_at.desc())
        .all()
    )


@router.post("/products", response_model=VendorProductPublic, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: VendorProductCreate,
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> VendorProduct:
    profile = _ensure_approved_vendor(db, user)
    tag_ids = _validate_product_tag_ids(profile, payload.tag_ids)

    data = payload.model_dump(exclude={"tag_ids"})
    product = VendorProduct(vendor_user_id=user.id, **data)
    db.add(product)
    db.flush()
    if tag_ids:
        _sync_product_tags(db, product, tag_ids)
    db.commit()

    refreshed = _load_product_with_tags(db, product.id) or product
    try:
        from app.services.vector_index import upsert_product_embedding

        upsert_product_embedding(db, product.id)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Product embedding refresh failed after create: %s", exc)
        db.rollback()
    db.refresh(refreshed)
    return refreshed


@router.get("/products/{product_id}", response_model=VendorProductPublic)
def get_product(
    product_id: int,
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> VendorProduct:
    _ensure_approved_vendor(db, user)
    product = _load_product_with_tags(db, product_id)
    if not product or product.vendor_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.patch("/products/{product_id}", response_model=VendorProductPublic)
def update_product(
    product_id: int,
    payload: VendorProductUpdate,
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> VendorProduct:
    profile = _ensure_approved_vendor(db, user)
    product = _load_product_with_tags(db, product_id)
    if not product or product.vendor_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    update_fields = payload.model_dump(exclude_unset=True, exclude={"tag_ids"})
    for field, value in update_fields.items():
        setattr(product, field, value)

    if payload.tag_ids is not None:
        tag_ids = _validate_product_tag_ids(profile, payload.tag_ids)
        _sync_product_tags(db, product, tag_ids)

    db.commit()
    refreshed = _load_product_with_tags(db, product.id) or product
    try:
        from app.services.vector_index import upsert_product_embedding

        upsert_product_embedding(db, product.id)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Product embedding refresh failed after update: %s", exc)
        db.rollback()
    db.refresh(refreshed)
    return refreshed


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> None:
    _ensure_approved_vendor(db, user)
    product = db.get(VendorProduct, product_id)
    if not product or product.vendor_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()
