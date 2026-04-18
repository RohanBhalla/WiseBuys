from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_current_vendor, get_db
from app.models import (
    User,
    UserRole,
    ValueTag,
    VendorApplication,
    VendorApplicationStatus,
    VendorApplicationTag,
    VendorProfile,
)
from app.schemas.vendor import (
    VendorApplicationCreate,
    VendorApplicationPublic,
    VendorProfilePublic,
)

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


def _validate_tag_ids(db: Session, tag_ids: list[int]) -> None:
    if not tag_ids:
        return
    found = db.query(ValueTag.id).filter(ValueTag.id.in_(tag_ids), ValueTag.is_active.is_(True)).all()
    found_ids = {row[0] for row in found}
    missing = [tid for tid in tag_ids if tid not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or inactive tag ids: {missing}",
        )


@router.post("/applications", response_model=VendorApplicationPublic, status_code=status.HTTP_201_CREATED)
def submit_application(
    payload: VendorApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VendorApplication:
    if user.role not in {UserRole.vendor, UserRole.customer}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot submit application")

    open_app = (
        db.query(VendorApplication)
        .filter(
            VendorApplication.applicant_user_id == user.id,
            VendorApplication.status.in_(
                [
                    VendorApplicationStatus.submitted,
                    VendorApplicationStatus.needs_info,
                ]
            ),
        )
        .first()
    )
    if open_app:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An open application (id={open_app.id}) already exists.",
        )

    _validate_tag_ids(db, payload.requested_tag_ids)

    application = VendorApplication(
        applicant_user_id=user.id,
        company_legal_name=payload.company_legal_name,
        company_website=str(payload.company_website) if payload.company_website else None,
        contact_email=str(payload.contact_email),
        country=payload.country,
        narrative=payload.narrative,
        evidence_urls=[str(u) for u in payload.evidence_urls] if payload.evidence_urls else None,
        status=VendorApplicationStatus.submitted,
    )
    db.add(application)
    db.flush()

    for tid in set(payload.requested_tag_ids):
        db.add(VendorApplicationTag(application_id=application.id, tag_id=tid))

    if user.role == UserRole.customer:
        user.role = UserRole.vendor

    db.commit()
    db.refresh(application)
    return application


@router.get("/applications/me", response_model=list[VendorApplicationPublic])
def list_my_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VendorApplication]:
    return (
        db.query(VendorApplication)
        .filter(VendorApplication.applicant_user_id == user.id)
        .order_by(VendorApplication.submitted_at.desc())
        .all()
    )


@router.get("/me", response_model=VendorProfilePublic)
def get_my_vendor_profile(
    user: User = Depends(get_current_vendor),
    db: Session = Depends(get_db),
) -> VendorProfile:
    profile = db.query(VendorProfile).filter(VendorProfile.user_id == user.id).one_or_none()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor profile not yet created. Application must be approved.",
        )
    return profile
