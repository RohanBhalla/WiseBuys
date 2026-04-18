from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development")
    app_name: str = Field(default="WiseBuys")
    secret_key: str = Field(default="dev-secret-change-me")
    access_token_expire_minutes: int = Field(default=60)
    algorithm: str = Field(default="HS256")

    database_url: str = Field(default="sqlite:///./wisebuys.db")

    bootstrap_admin_email: str | None = Field(default=None)
    bootstrap_admin_password: str | None = Field(default=None)

    knot_client_id: str | None = Field(default=None)
    knot_secret: str | None = Field(default=None)
    knot_environment: str = Field(default="development")

    gemini_api_key: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
