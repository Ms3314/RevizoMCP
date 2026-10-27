import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.models import Base

load_dotenv()

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and paste your "
        "Supabase Session Pooler connection string (port 5432)."
    )


def _make_engine():
    kwargs = {"pool_pre_ping": True}
    if DATABASE_URL.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(DATABASE_URL, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# create_all never alters a table that already exists, so columns added after a
# table first shipped are backfilled here. Postgres DDL (production DB).
ADDED_COLUMNS = {
    "attempts": {
        "diagnosis": "TEXT NOT NULL DEFAULT ''",
        "concepts": "JSONB NOT NULL DEFAULT '[]'::jsonb",
        "weakness_kind": "VARCHAR",
    },
}


def _add_missing_columns() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    """Create tables if they don't exist and add any newer columns (idempotent)."""
    Base.metadata.create_all(engine)
    _add_missing_columns()


def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
