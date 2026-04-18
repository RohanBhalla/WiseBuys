import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_wisebuys.db")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@wisebuys.example.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "AdminPass123!")

from app import database as database_module  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seeds.admin import bootstrap_admin  # noqa: E402
from app.seeds.tags import seed_tags  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _configure_settings():
    get_settings.cache_clear()
    yield


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    db_file = tmp_path / "wb_test.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()

    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", TestingSession)

    Base.metadata.create_all(bind=engine)

    db = TestingSession()
    seed_tags(db)
    bootstrap_admin(db)
    db.close()

    def _override_get_db():
        d = TestingSession()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session) -> TestClient:
    return TestClient(app)


def auth_headers(client: TestClient, email: str, password: str, role: str | None = None) -> dict:
    if role:
        client.post("/api/auth/register", json={"email": email, "password": password, "role": role})
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
