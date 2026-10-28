"""SQLAlchemy engine, session factory and FastAPI session dependency.

The database is Supabase-hosted PostgreSQL. There is intentionally no SQLite
fallback: if ``DATABASE_URL`` is not configured, the application still starts
(so ``/api/health`` and the docs work) but every database-backed endpoint
returns a clear configuration error.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Query parameters understood by SQLAlchemy/psycopg. Anything else that appears
# in a copied connection string (for example Prisma's ``pgbouncer`` flag) is
# dropped, otherwise psycopg rejects it as an unknown libpq parameter.
_SUPPORTED_QUERY_PARAMS = {
    "sslmode",
    "sslrootcert",
    "sslcert",
    "sslkey",
    "sslcrl",
    "application_name",
    "connect_timeout",
    "options",
    "target_session_attrs",
    "keepalives",
    "keepalives_idle",
    "keepalives_interval",
    "keepalives_count",
}

# Driver-specific query parameters that must be removed before handing the URL
# to SQLAlchemy's psycopg dialect.
_DROPPED_QUERY_PARAMS = {"pgbouncer", "supa", "schema", "prepare_threshold"}


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a database operation is attempted without ``DATABASE_URL``."""


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy URL using the psycopg v3 driver.

    Accepts the formats Supabase hands out (``postgres://`` and
    ``postgresql://``) and leaves an explicitly configured driver untouched.
    Unknown query parameters are removed so that copy-pasted connection strings
    from other tools do not break the driver.
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    if not parts.query:
        return url

    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key in _SUPPORTED_QUERY_PARAMS and key not in _DROPPED_QUERY_PARAMS
    ]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use.

    ``create_engine`` is lazy: it does not open a connection until a session is
    actually used, so importing the app never touches the network.
    """
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise DatabaseNotConfiguredError(
                "DATABASE_URL is not configured. Set it in backend/.env to the "
                "Supabase PostgreSQL connection string."
            )
        try:
            _engine = create_engine(
                normalize_database_url(settings.database_url),
                pool_pre_ping=True,
                future=True,
            )
        except Exception as exc:
            raise DatabaseNotConfiguredError(
                "DATABASE_URL is not a valid PostgreSQL connection string."
            ) from exc
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the session factory bound to the lazily created engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _session_factory


def get_db() -> Generator[Session, Any, None]:
    """FastAPI dependency that yields a session and always closes it.

    A missing or invalid ``DATABASE_URL`` becomes a 503 with a configuration
    hint rather than an unhandled 500, so a copied ``.env.example`` produces an
    understandable error instead of a stack trace.
    """
    try:
        session = get_session_factory()()
    except DatabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    try:
        yield session
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose and forget the cached engine (used by tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
