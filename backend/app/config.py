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
    # When true, /api/knot/webhooks rejects requests missing or with a bad
    # `Knot-Signature` header (HMAC-SHA256). Defaults to False so local dev
    # without a configured secret keeps working; set True for production.
    knot_webhook_require_signature: bool = Field(default=False)
    # Public URL Knot should POST to. Informational only; the actual
    # subscription is configured in the Knot dashboard.
    knot_webhook_url: str | None = Field(default=None)
    # When true, the dev-only /api/knot/dev/* simulation endpoints are
    # exposed (see Backend/app/routers/knot.py). They call Knot's
    # /development/accounts/{link,disconnect} endpoints which only work
    # against the development environment.
    knot_dev_simulation_enabled: bool = Field(default=True)

    gemini_api_key: str | None = Field(default=None)

    # Hybrid vector recommendations (Postgres + pgvector + Gemini embeddings).
    embeddings_model: str = Field(default="gemini-embedding-001")
    embeddings_dim: int = Field(default=768)
    vector_recs_enabled: bool = Field(default=True)
    vector_candidate_pool: int = Field(default=50)
    vector_rec_weight_vec: float = Field(default=4.0)
    vector_rec_weight_primary: float = Field(default=3.0)
    vector_rec_weight_secondary: float = Field(default=1.0)
    vector_rec_weight_category: float = Field(default=1.5)
    vector_rec_weight_token_overlap: float = Field(default=0.5)
    vector_rec_weight_recency: float = Field(default=0.35)
    embeddings_batch_size: int = Field(default=32)
    embeddings_max_retries: int = Field(default=4)
    # Soft per-minute cap on Gemini embedding requests. The free tier on
    # ``gemini-embedding-001`` allows 100 RPM; we self-throttle to stay below
    # that with headroom. Bump this on a paid tier.
    embeddings_max_rpm: int = Field(default=90)
    # Minimum gap (seconds) the embedding limiter enforces between
    # consecutive requests. Helps avoid bursting into the API even when
    # we're under the per-minute cap; set to 0 to disable.
    embeddings_min_interval_s: float = Field(default=2.0)

    # When true, bootstraps approved demo vendors + catalog (see app/seeds/demo_vendors.py).
    seed_demo_vendors: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
