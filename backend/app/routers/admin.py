from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import get_current_admin, get_db
from app.models import (
    User,
    UserRole,
    ValueTag,
    VendorAllowedTag,
    VendorApplication,
    VendorApplicationStatus,
    VendorProfile,
)
from app.schemas.vendor import VendorApplicationDecision, VendorApplicationPublic

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/applications", response_model=list[VendorApplicationPublic])
def list_applications(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
    status_filter: VendorApplicationStatus | None = Query(default=None, alias="status"),
) -> list[VendorApplication]:
    query = db.query(VendorApplication).order_by(VendorApplication.submitted_at.desc())
    if status_filter:
        query = query.filter(VendorApplication.status == status_filter)
    return query.all()


@router.get("/applications/{application_id}", response_model=VendorApplicationPublic)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> VendorApplication:
    app_obj = db.get(VendorApplication, application_id)
    if not app_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app_obj


@router.post("/applications/{application_id}/decision", response_model=VendorApplicationPublic)
def decide_application(
    application_id: int,
    decision: VendorApplicationDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> VendorApplication:
    app_obj = db.get(VendorApplication, application_id)
    if not app_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if app_obj.status in {VendorApplicationStatus.approved, VendorApplicationStatus.rejected}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Application already finalized as {app_obj.status.value}",
        )

    if decision.status not in {
        VendorApplicationStatus.approved,
        VendorApplicationStatus.rejected,
        VendorApplicationStatus.needs_info,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision status must be approved, rejected, or needs_info",
        )

    if decision.status == VendorApplicationStatus.approved:
        if not decision.allowed_tag_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="allowed_tag_ids is required when approving",
            )

        tags = (
            db.query(ValueTag)
            .filter(ValueTag.id.in_(decision.allowed_tag_ids), ValueTag.is_active.is_(True))
            .all()
        )
        found_ids = {t.id for t in tags}
        missing = [tid for tid in decision.allowed_tag_ids if tid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown or inactive allowed_tag_ids: {missing}",
            )

        applicant = db.get(User, app_obj.applicant_user_id)
        if not applicant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant user missing")
        applicant.role = UserRole.vendor

        profile = (
            db.query(VendorProfile).filter(VendorProfile.user_id == applicant.id).one_or_none()
        )
        if not profile:
            profile = VendorProfile(
                user_id=applicant.id,
                company_legal_name=app_obj.company_legal_name,
                company_website=app_obj.company_website,
                country=app_obj.country,
                application_id=app_obj.id,
            )
            db.add(profile)
            db.flush()
        else:
            profile.company_legal_name = app_obj.company_legal_name
            profile.company_website = app_obj.company_website
            profile.country = app_obj.country
            profile.application_id = app_obj.id

        db.query(VendorAllowedTag).filter(VendorAllowedTag.vendor_profile_id == profile.id).delete()
        db.flush()
        for tid in set(decision.allowed_tag_ids):
            db.add(VendorAllowedTag(vendor_profile_id=profile.id, tag_id=tid))

    app_obj.status = decision.status
    app_obj.admin_notes = decision.admin_notes
    app_obj.reviewed_by_user_id = admin.id
    app_obj.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(app_obj)
    return app_obj
