"""Hybrid / vector recommendation plumbing (SQLite CI + optional Postgres)."""

from __future__ import annotations

import os

import pytest

from app.database import db_is_postgresql
from app.services import recommendations as rec_mod
from app.services.vector_index import upsert_customer_embedding, upsert_product_embedding

from tests.conftest import auth_headers


def test_db_is_sqlite_in_default_fixture(db_session):
    db = db_session()
    assert db_is_postgresql(db) is False


def test_vector_upserts_noop_on_sqlite(db_session):
    db = db_session()
    assert upsert_customer_embedding(db, 999) is False
    assert upsert_product_embedding(db, 999) is False


def test_recommendations_me_ok_sqlite(client, db_session):
    headers = auth_headers(client, "vec_rec_cust@example.com", "CustPass123!", "customer")
    res = client.get("/api/recommendations/me", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_recommend_for_user_rules_only_excludes_ids(db_session):
    """Smoke-test rules helper with empty exclude set (no crash)."""
    from app.models import User, UserRole

    db = db_session()
    u = User(email="rules_only@example.com", password_hash="x", role=UserRole.customer)
    db.add(u)
    db.commit()
    out = rec_mod.recommend_for_user_rules_only(db, u, limit=5, exclude_product_ids={999999})
    assert isinstance(out, list)


@pytest.mark.skipif(
    os.getenv("RUN_PGVECTOR_TESTS") != "1",
    reason="Set RUN_PGVECTOR_TESTS=1 and DATABASE_URL=postgresql+psycopg://... to run pgvector tests",
)
def test_hybrid_path_requires_postgres_and_embeddings(db_session):
    db = db_session()
    if not db_is_postgresql(db):
        pytest.skip("Not using PostgreSQL")
    # Integration point: hybrid returns [] without embeddings populated.
    from app.models import User, UserRole

    u = db.query(User).filter(User.email == "pg_hybrid@example.com").one_or_none()
    if u is None:
        u = User(email="pg_hybrid@example.com", password_hash="x", role=UserRole.customer)
        db.add(u)
        db.commit()
    hybrid = rec_mod.recommend_for_user_hybrid(db, u, limit=5)
    assert isinstance(hybrid, list)
