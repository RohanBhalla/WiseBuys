from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.tag import TagPublic


class RewardsPreferences(BaseModel):
    """Open shape so we can iterate without breaking storage."""

    mode: str | None = Field(default=None, description="e.g. points, cashback, perks")
    tiers_interest: bool | None = None
    notes: str | None = None


class CustomerProfileUpdate(BaseModel):
    primary_focus_tag_id: int | None = None
    secondary_focus_tag_ids: list[int] | None = None
    rewards_preferences: RewardsPreferences | None = None


class CustomerProfilePublic(BaseModel):
    id: int
    user_id: int
    primary_focus: TagPublic | None = None
    secondary_focuses: list[TagPublic] = []
    rewards_preferences: dict | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _flatten_secondary_focuses(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data

        secondary = getattr(data, "secondary_focuses", None)
        if secondary is None:
            return data

        flattened = [link.tag for link in secondary if getattr(link, "tag", None) is not None]
        return {
            "id": data.id,
            "user_id": data.user_id,
            "primary_focus": getattr(data, "primary_focus", None),
            "secondary_focuses": flattened,
            "rewards_preferences": getattr(data, "rewards_preferences", None),
        }
