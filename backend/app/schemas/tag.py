from pydantic import BaseModel, Field


class TagBase(BaseModel):
    slug: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=2, max_length=128)
    description: str | None = None
    category: str | None = None
    is_active: bool = True


class TagCreate(TagBase):
    pass


class TagPublic(TagBase):
    id: int

    model_config = {"from_attributes": True}
