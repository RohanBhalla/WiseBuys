from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole

    model_config = {"use_enum_values": False}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}
