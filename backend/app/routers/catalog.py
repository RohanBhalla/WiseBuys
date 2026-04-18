from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_vendor, get_db
from app.models import User, VendorProduct, VendorProfile
from app.schemas.catalog import VendorProductCreate, VendorProductPublic, VendorProductUpdate

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _ensure_approved_vendor(db: Session, user: User) -> VendorProfile:
    profile = db.query(VendorProfile).filter(VendorProfile.user_id == user.id).one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vendor must be approved before managing catalog.",
        )
    return profile


@router.get("/products", response_model=list[VendorProductPublic])
def list_my_products(
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> list[VendorProduct]:
    _ensure_approved_vendor(db, user)
    return (
        db.query(VendorProduct)
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
    _ensure_approved_vendor(db, user)
    product = VendorProduct(
        vendor_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=VendorProductPublic)
def get_product(
    product_id: int,
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> VendorProduct:
    _ensure_approved_vendor(db, user)
    product = db.get(VendorProduct, product_id)
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
    _ensure_approved_vendor(db, user)
    product = db.get(VendorProduct, product_id)
    if not product or product.vendor_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


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
