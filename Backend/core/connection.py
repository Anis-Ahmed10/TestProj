"""SQLAlchemy PostgreSQL connection helper.

This module creates a shared SQLAlchemy engine and session factory that can be
used for both local PostgreSQL and the managed RDS instance.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

Base = declarative_base()
_last_connection_version: str | None = None


def resolve_db_password() -> str:
    """Return the database password, supplied as an environment variable."""
    password = get_settings().db_password
    if not password:
        raise RuntimeError("DB_PASSWORD is not set")
    return password


def build_database_url() -> str:
    """Build the SQLAlchemy database URL from application settings."""
    settings = get_settings()
    return (
        f"postgresql+psycopg2://{settings.db_user}:"
        f"{quote_plus(resolve_db_password())}@"
        f"{settings.db_host}:{settings.db_port}/"
        f"{settings.db_name}"
    )


def build_connect_args() -> dict[str, str]:
    """Build optional SQLAlchemy connect arguments."""
    settings = get_settings()
    args: dict[str, str] = {}
    if settings.db_sslmode:
        args["sslmode"] = settings.db_sslmode
    if settings.db_sslrootcert:
        args["sslrootcert"] = settings.db_sslrootcert
    return args


def create_postgres_engine() -> Engine:
    """Create the shared SQLAlchemy engine."""
    return create_engine(
        build_database_url(),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        pool_recycle=900,
        connect_args=build_connect_args(),
    )


_session_factory: sessionmaker | None = None


def SessionLocal() -> Session:
    """Open a session, building the engine on first use.

    Every model imports ``Base`` from this module, so creating the engine at
    import time made DB credentials a requirement for importing anything.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=create_postgres_engine()
        )
    return _session_factory()


def get_db() -> Iterator[Session]:
    """Yield a SQLAlchemy session and close it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def postgres_session() -> Iterator[Session]:
    """Context manager for ad hoc database access."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    """Run a lightweight health check query against PostgreSQL."""
    global _last_connection_version
    _last_connection_version = None

    with postgres_session() as db:
        result = db.execute(text("SELECT version()"))
        version = getattr(result, "scalar_one_or_none", lambda: None)()
        if isinstance(version, str):
            _last_connection_version = version
        db.commit()
    return True


def main() -> None:
    """Run the module as a small PostgreSQL connectivity check."""
    try:
        if test_connection():
            print("Connected to PostgreSQL successfully.")
            if _last_connection_version:
                print(_last_connection_version)
    except Exception as exc:
        print(f"Failed to connect to PostgreSQL: {exc}")


if __name__ == "__main__":
    main()
