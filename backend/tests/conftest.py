"""Shared pytest fixtures.

Tests never contact Supabase or the AI provider: authentication is verified
with locally generated keys, the database is an in-memory SQLite database, and
the agent service is replaced through FastAPI dependency overrides.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import CurrentUser, get_current_user
from app.main import app
from app.schemas.agent import AgentOutput
from app.services.ai_agent import AIAgentService


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Start every test with no integrations configured."""
    for name in (
        "database_url",
        "supabase_url",
        "supabase_jwks_url",
        "supabase_jwt_secret",
        "openai_api_key",
    ):
        monkeypatch.setattr(settings, name, None, raising=False)
    monkeypatch.setattr(settings, "auto_create_tables", False, raising=False)
    monkeypatch.setattr(settings, "openai_model", "test-model", raising=False)
    monkeypatch.setattr(
        settings, "supabase_jwt_audience", "authenticated", raising=False
    )
    yield


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
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Test client with database and authentication dependencies overridden."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_current_user() -> CurrentUser:
        return CurrentUser(user_id="test-user-id", claims={"sub": "test-user-id"})

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeAgentService(AIAgentService):
    """Deterministic stand-in for the real agent service."""

    def __init__(
        self, result: AgentOutput | None = None, error: Exception | None = None
    ) -> None:
        super().__init__(api_key="unused", model="test-model")
        self.result = result or AgentOutput(
            answer="A vector database stores embeddings and searches them by similarity.",
            key_points=["Stores vectors", "Nearest-neighbour search"],
            follow_up_questions=["How do embeddings work?"],
        )
        self.error = error
        self.prompts: list[str] = []

    def run(self, prompt: str) -> AgentOutput:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def fake_agent() -> FakeAgentService:
    return FakeAgentService()


@pytest.fixture
def utc_now() -> datetime:
    return datetime.now(UTC)


def build_agent_override(service: Any):
    """Create a FastAPI dependency override returning ``service``."""

    def _override() -> Any:
        return service

    return _override
