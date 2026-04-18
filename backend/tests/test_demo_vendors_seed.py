"""Tests for optional demo vendor seed (Knot / recommendation QA)."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.models import User, VendorProduct
from app.seeds.admin import bootstrap_admin
from app.seeds.demo_vendors import seed_demo_vendors
from app.seeds.tags import seed_tags


def test_seed_demo_vendors_idempotent(db_session, monkeypatch):
    monkeypatch.setenv("SEED_DEMO_VENDORS", "true")
    get_settings.cache_clear()

    db = db_session()
    seed_tags(db)
    bootstrap_admin(db)

    assert seed_demo_vendors(db) == 4
    assert seed_demo_vendors(db) == 0

    users = db.query(User).filter(User.email.startswith("demo.v.")).all()
    assert len(users) == 4
    products = db.query(VendorProduct).filter(VendorProduct.sku.like("DEMO-%")).all()
    assert len(products) >= 8
    db.close()
