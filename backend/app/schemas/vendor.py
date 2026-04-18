from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, HttpUrl, model_validator

from app.models.vendor import VendorApplicationStatus
from app.schemas.tag import TagPublic


class VendorApplicationCreate(BaseModel):
    company_legal_name: str = Field(min_length=2, max_length=255)
    company_website: HttpUrl | None = None
    contact_email: EmailStr
    country: str | None = Field(default=None, min_length=2, max_length=2)
    narrative: str | None = Field(default=None, max_length=4000)
    requested_tag_ids: list[int] = Field(default_factory=list)
    evidence_urls: list[HttpUrl] = Field(default_factory=list)


class VendorApplicationPublic(BaseModel):
    id: int
    applicant_user_id: int
    company_legal_name: str
    company_website: str | None
    contact_email: str
    country: str | None
    narrative: str | None
    evidence_urls: list[str] | None
    status: VendorApplicationStatus
    admin_notes: str | None = None
    requested_tags: list[TagPublic] = []
    submitted_at: datetime
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _flatten_requested_tags(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        requested = getattr(data, "requested_tags", None)
        if requested is None:
            return data
        return {
            "id": data.id,
            "applicant_user_id": data.applicant_user_id,
            "company_legal_name": data.company_legal_name,
            "company_website": data.company_website,
            "contact_email": data.contact_email,
            "country": data.country,
            "narrative": data.narrative,
            "evidence_urls": data.evidence_urls,
            "status": data.status,
            "admin_notes": data.admin_notes,
            "requested_tags": [link.tag for link in requested if getattr(link, "tag", None)],
            "submitted_at": data.submitted_at,
            "reviewed_at": data.reviewed_at,
        }


class VendorApplicationDecision(BaseModel):
    """Used by admin endpoints to transition status."""

    status: VendorApplicationStatus
    admin_notes: str | None = None
    allowed_tag_ids: list[int] | None = Field(
        default=None,
        description="Required when approving. Subset of requested_tag_ids (or any active tag).",
    )


class VendorProfilePublic(BaseModel):
    id: int
    user_id: int
    company_legal_name: str
    company_website: str | None
    country: str | None
    allowed_tags: list[TagPublic] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _flatten_allowed_tags(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        allowed = getattr(data, "allowed_tags", None)
        if allowed is None:
            return data
        return {
            "id": data.id,
            "user_id": data.user_id,
            "company_legal_name": data.company_legal_name,
            "company_website": data.company_website,
            "country": data.country,
            "allowed_tags": [link.tag for link in allowed if getattr(link, "tag", None)],
        }
