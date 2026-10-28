"""Database routing: one directory database for logins, one database per client.

Every client's accounts and transactions live in their own PostgreSQL database
(``client_<username>``); the directory database only maps usernames to those
databases. URLs are derived from ``DATABASE_ADMIN_URL`` by swapping the
database name. Tests replace the router with one that hands out SQLite engines.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Generator
from threading import Lock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
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


_DATABASE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class DirectoryBase(DeclarativeBase):
    """Tables of the directory database (logins)."""


class ClientBase(DeclarativeBase):
    """Tables of each client's own database."""


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


def database_url(admin_url: str, database: str) -> str:
    """The admin URL pointing at another database on the same server."""
    if not _DATABASE_NAME.match(database):
        raise ValueError(f"Invalid database name: {database!r}")
    url = make_url(normalize_database_url(admin_url)).set(database=database)
    return url.render_as_string(hide_password=False)


class DatabaseRouter:
    """Creates and caches one engine per database."""

    def __init__(
        self,
        admin_url: str | None = None,
        engine_factory: Callable[[str], Engine] | None = None,
        create_databases: bool = True,
    ) -> None:
        self._admin_url = admin_url or settings.database_admin_url
        self._engine_factory = engine_factory or (
            lambda url: create_engine(
                url, pool_pre_ping=True, pool_size=2, max_overflow=3
            )
        )
        # False when the factory makes self-contained databases (SQLite in tests).
        self._create_databases = create_databases
        self._engines: dict[str, Engine] = {}
        self._factories: dict[str, sessionmaker[Session]] = {}
        self._lock = Lock()

    def admin_engine(self) -> Engine:
        """Server-level connection, autocommit so CREATE DATABASE works."""
        return self.engine("__admin__")

    def engine(self, database: str) -> Engine:
        with self._lock:
            if database not in self._engines:
                if database == "__admin__":
                    engine = create_engine(
                        normalize_database_url(self._admin_url),
                        isolation_level="AUTOCOMMIT",
                        pool_pre_ping=True,
                    )
                else:
                    engine = self._engine_factory(
                        database_url(self._admin_url, database)
                    )
                self._engines[database] = engine
            return self._engines[database]

    def ensure_database(self, database: str) -> bool:
        """Create the database on the server if missing. True if it was created."""
        if not self._create_databases:
            return False
        database_url(self._admin_url, database)  # validates the name
        with self.admin_engine().connect() as conn:
            exists = conn.exec_driver_sql(
                "SELECT 1 FROM pg_database WHERE datname = %(name)s", {"name": database}
            ).scalar()
            if exists:
                return False
            # Name validated above; identifiers cannot be bound as parameters.
            conn.exec_driver_sql(f'CREATE DATABASE "{database}"')
            return True

    def session(self, database: str) -> Session:
        engine = self.engine(database)
        with self._lock:
            if database not in self._factories:
                self._factories[database] = sessionmaker(
                    bind=engine, autoflush=False, expire_on_commit=False
                )
            return self._factories[database]()

    def directory_session(self) -> Session:
        return self.session(settings.directory_database)

    def dispose(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()
            self._factories.clear()


router = DatabaseRouter()


def get_router() -> DatabaseRouter:
    """FastAPI dependency; tests override it."""
    return router


def session_scope(session: Session) -> Generator[Session, None, None]:
    try:
        yield session
    finally:
        session.close()
