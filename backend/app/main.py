from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import *  # noqa: F401,F403  (ensure models are registered before create_all)
from app.routers import (
    admin,
    auth,
    catalog,
    customers,
    health,
    knot,
    knot_webhooks,
    recommendations,
    rewards,
    tags,
    vendors,
)
from app.seeds.admin import bootstrap_admin
from app.seeds.demo_vendors import seed_demo_vendors
from app.seeds.tags import seed_tags


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_tags(db)
        bootstrap_admin(db)
        seed_demo_vendors(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description=(
            "WiseBuys backend: customer onboarding (focuses, rewards prefs), "
            "vendor application + vetting, platform-controlled value tags, and vendor catalog."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tags.router)
    app.include_router(customers.router)
    app.include_router(vendors.router)
    app.include_router(catalog.router)
    app.include_router(admin.router)
    app.include_router(knot.router)
    app.include_router(knot_webhooks.router)
    app.include_router(recommendations.router)
    app.include_router(recommendations.insights_router)
    app.include_router(rewards.router)
    app.include_router(rewards.admin_router)

    return app


app = create_app()
