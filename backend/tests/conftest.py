"""Shared pytest fixtures.

Tests never contact the AI provider or a real database: the database is an
in-memory SQLite database, the agent service runs without a key (rules
fallback) unless a test injects a stub client, and every test gets a fresh
in-memory demo state.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_agent_service, get_demo_state
from app.core.config import settings
from app.core.database import Base, maybe_get_db
from app.main import app
from app.schemas.banking import ClientSnapshot
from app.services.ai_agent import AIAgentService
from app.services.banking.executor import DemoState
from app.services.banking.loader import load_snapshot


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Start every test with no integrations configured and the bundled data."""
    for name in ("database_url", "openai_api_key", "demo_data_path", "demo_today"):
        monkeypatch.setattr(settings, name, None, raising=False)
    monkeypatch.setattr(settings, "auto_create_tables", False, raising=False)
    monkeypatch.setattr(settings, "openai_model", "test-model", raising=False)
    yield


@pytest.fixture
def snapshot() -> ClientSnapshot:
    return load_snapshot()


@pytest.fixture
def state() -> DemoState:
    return DemoState()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """A session bound to an isolated in-memory SQLite database."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session, state: DemoState) -> Generator[TestClient, None, None]:
    """Test client with database, demo state and agent service overridden."""

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[maybe_get_db] = override_db
    app.dependency_overrides[get_demo_state] = lambda: state
    app.dependency_overrides[get_agent_service] = lambda: AIAgentService(api_key=None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
