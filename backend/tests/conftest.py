"""Shared pytest fixtures.

Tests never contact PostgreSQL or Amazon Bedrock: the database router hands
each user (and the directory) its own in-memory SQLite database, provisioned
from the real seed files; the agent service has no AWS credentials (rules
fallback) unless a test injects a stub Bedrock client; payment approval runs
on a clock the tests advance by hand.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_agent_service, get_challenge_store
from app.core import security
from app.core.config import settings
from app.core.database import DatabaseRouter, get_router
from app.main import app
from app.schemas.banking import ClientSnapshot
from app.services.ai_agent import AIAgentService
from app.services.banking.executor import ChallengeStore
from app.services.banking.loader import load_snapshot
from app.services.provisioning import provision

DEMO_PASSWORD = "overdraft2026"


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """No integrations, a fixed session secret, and cheap password hashing."""
    # Real AWS credentials in backend/.env must never reach the tests.
    for name in (
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "demo_today",
    ):
        monkeypatch.setattr(settings, name, None)
    monkeypatch.setattr(settings, "bedrock_model_id", "test-model")
    monkeypatch.setattr(settings, "session_secret", "test-secret")
    monkeypatch.setattr(settings, "provision_on_startup", False)
    monkeypatch.setattr(settings, "demo_approval_seconds", 3.0)
    monkeypatch.setattr(security, "_SCRYPT", {"n": 2**4, "r": 8, "p": 1, "dklen": 32})
    yield


class FakeClock:
    """Monotonic clock the tests advance by hand, so approval never sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def snapshot() -> ClientSnapshot:
    return load_snapshot()


def _sqlite(_: str) -> Engine:
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def db_router() -> Generator[DatabaseRouter, None, None]:
    """Every seed user provisioned into their own in-memory database."""
    router = DatabaseRouter(
        admin_url="postgresql://test:test@localhost/postgres",
        engine_factory=_sqlite,
        create_databases=False,
    )
    provision(router)
    yield router
    router.dispose()


@pytest.fixture
def store(clock: FakeClock) -> ChallengeStore:
    return ChallengeStore(clock=clock)


@pytest.fixture
def client(
    db_router: DatabaseRouter, store: ChallengeStore
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_router] = lambda: db_router
    app.dependency_overrides[get_challenge_store] = lambda: store
    app.dependency_overrides[get_agent_service] = lambda: AIAgentService()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(client: TestClient, username: str = "andrei") -> dict[str, str]:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def andrei(client: TestClient) -> dict[str, str]:
    return auth_headers(client, "andrei")
