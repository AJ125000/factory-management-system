"""Database engine, sessions and automatic migrations."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def make_engine(url: str, *, foreign_keys: bool = True) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        # Enforce relations (off by default in SQLite).
        cur.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}")
        cur.execute("PRAGMA journal_mode=WAL")  # crash-safe, readers don't block writers
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


class MigrationIntegrityError(RuntimeError):
    pass


def run_migrations(url: str) -> None:
    """Bring the database schema up to date. Safe to run on every start.

    Runs with foreign keys OFF: SQLite migrations rebuild tables, and dropping a
    table with foreign keys ON would cascade-delete rows in related tables.
    Integrity is checked afterwards instead.
    """
    engine = make_engine(url, foreign_keys=False)
    try:
        cfg = alembic_config()
        with engine.begin() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
            problems = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if problems:
                raise MigrationIntegrityError(f"Foreign key violations after migration: {problems}")
    finally:
        engine.dispose()


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency. Routes commit explicitly; anything uncommitted is rolled back."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
