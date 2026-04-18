"""Backfill Gemini embeddings for published products and customer profiles.

Usage (from the backend directory):

    PYTHONPATH=. python -m app.scripts.embed_backfill

Works with **SQLite** or **Postgres**. Requires ``GEMINI_API_KEY`` and
``VECTOR_RECS_ENABLED=true`` (default). Postgres production should still run
``CREATE EXTENSION vector`` and ``alembic upgrade head`` for IVFFlat ANN; SQLite
stores vectors without the extension.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.database import SessionLocal
from app.services.vector_index import backfill_all_embeddings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    if not settings.vector_recs_enabled:
        logger.error("VECTOR_RECS_ENABLED is false — enable hybrid recs before backfill.")
        raise SystemExit(1)
    key = settings.gemini_api_key
    if not (key and str(key).strip()):
        logger.error("GEMINI_API_KEY is required for embedding backfill.")
        raise SystemExit(1)

    db = SessionLocal()
    try:
        out = backfill_all_embeddings(db)
        logger.info("Backfill complete: %s", out)
    finally:
        db.close()


if __name__ == "__main__":
    main()
