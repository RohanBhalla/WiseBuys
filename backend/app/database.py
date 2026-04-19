from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


_settings = get_settings()
engine = create_engine(_settings.database_url, future=True, **_engine_kwargs(_settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def ensure_sqlite_embedding_columns(engine) -> None:
    """SQLite dev DBs created before hybrid recs: ``create_all`` never alters existing tables.

    Adds ``embedding`` / ``embedding_signature`` / ``embedded_at`` when missing so ORM
    queries match the on-disk schema. No-op for Postgres (use Alembic there).
    """
    if engine.dialect.name != "sqlite":
        return

    tables = ("customer_profiles", "vendor_products", "knot_line_items")
    with engine.begin() as conn:
        for table in tables:
            res = conn.execute(text(f'PRAGMA table_info("{table}")'))
            existing = {row[1] for row in res.fetchall()}
            if not existing:
                continue
            if "embedding" not in existing:
                conn.execute(
                    text(f'ALTER TABLE "{table}" ADD COLUMN embedding VECTOR(768)')
                )
            if "embedding_signature" not in existing:
                conn.execute(
                    text(f'ALTER TABLE "{table}" ADD COLUMN embedding_signature TEXT')
                )
            if "embedded_at" not in existing:
                conn.execute(
                    text(f'ALTER TABLE "{table}" ADD COLUMN embedded_at DATETIME')
                )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_is_postgresql(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"
