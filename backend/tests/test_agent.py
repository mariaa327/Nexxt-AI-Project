"""Agent endpoint and service tests (no network, no real credentials)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.endpoints.agent import get_agent_service
from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.main import app
from app.models.domain import AgentTask
from app.schemas.agent import AgentOutput
from app.services.ai_agent import (
    AgentConfigurationError,
    AgentEmptyResponseError,
    AgentProviderError,
    AgentRefusalError,
    AIAgentService,
)
from tests.conftest import FakeAgentService


@pytest.fixture
def agent_client(
    db_session: Session, fake_agent: FakeAgentService
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent_service] = lambda: fake_agent
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="test-user-id", claims={"sub": "test-user-id"}
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_agent_run_persists_task_for_authenticated_user(
    agent_client: TestClient, db_session: Session, fake_agent: FakeAgentService
) -> None:
    response = agent_client.post(
        "/api/agent/run", json={"prompt": "Explain embeddings"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["result"]["answer"] == fake_agent.result.answer
    assert body["result"]["key_points"] == fake_agent.result.key_points
    assert body["id"]

    task = db_session.query(AgentTask).one()
    assert task.user_id == "test-user-id"
    assert task.prompt == "Explain embeddings"
    assert task.result["answer"] == fake_agent.result.answer
    assert task.created_at is not None


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t "])
def test_agent_run_rejects_blank_prompt(agent_client: TestClient, prompt: str) -> None:
    response = agent_client.post("/api/agent/run", json={"prompt": prompt})

    assert response.status_code == 422


def test_agent_run_rejects_prompt_over_limit(agent_client: TestClient) -> None:
    response = agent_client.post("/api/agent/run", json={"prompt": "a" * 5000})

    assert response.status_code == 422


def test_agent_run_returns_503_when_ai_not_configured(
    agent_client: TestClient, fake_agent: FakeAgentService
) -> None:
    fake_agent.error = AgentConfigurationError()

    response = agent_client.post("/api/agent/run", json={"prompt": "Hello"})

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_agent_run_returns_502_on_provider_error(
    agent_client: TestClient, fake_agent: FakeAgentService
) -> None:
    fake_agent.error = AgentProviderError()

    response = agent_client.post("/api/agent/run", json={"prompt": "Hello"})

    assert response.status_code == 502
    # No provider internals or stack traces leak to the client.
    assert "Traceback" not in response.text
    assert "sk-" not in response.text


def test_agent_run_returns_422_on_refusal(
    agent_client: TestClient, fake_agent: FakeAgentService
) -> None:
    fake_agent.error = AgentRefusalError()

    response = agent_client.post("/api/agent/run", json={"prompt": "Hello"})

    assert response.status_code == 422


def test_agent_run_does_not_persist_on_failure(
    agent_client: TestClient, db_session: Session, fake_agent: FakeAgentService
) -> None:
    fake_agent.error = AgentProviderError()

    agent_client.post("/api/agent/run", json={"prompt": "Hello"})

    assert db_session.query(AgentTask).count() == 0


def test_agent_run_requires_database_configuration(
    monkeypatch: pytest.MonkeyPatch, fake_agent: FakeAgentService
) -> None:
    """Without DATABASE_URL the endpoint fails clearly instead of using SQLite."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "database_url", None, raising=False)
    app.dependency_overrides[get_agent_service] = lambda: fake_agent
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="test-user-id", claims={"sub": "test-user-id"}
    )
    try:
        with TestClient(app) as client:
            response = client.post("/api/agent/run", json={"prompt": "Hello"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]


# --- Service unit tests ----------------------------------------------------


class _StubResponse:
    def __init__(
        self,
        parsed: AgentOutput | None,
        status: str = "completed",
        refusal: bool = False,
    ) -> None:
        self.output_parsed = parsed
        self.status = status
        self.output: list[Any] = []
        if refusal:
            self.output = [
                type(
                    "Item",
                    (),
                    {"content": [type("Content", (), {"type": "refusal"})()]},
                )()
            ]


class _StubResponses:
    def __init__(self, response: _StubResponse | Exception) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> _StubResponse:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _StubClient:
    def __init__(self, response: _StubResponse | Exception) -> None:
        self.responses = _StubResponses(response)


def _output() -> AgentOutput:
    return AgentOutput(answer="Answer", key_points=["a"], follow_up_questions=[])


def test_service_requires_api_key() -> None:
    service = AIAgentService(api_key=None)

    with pytest.raises(AgentConfigurationError):
        service.run("Hello")


def test_service_returns_parsed_output() -> None:
    client = _StubClient(_StubResponse(_output()))
    service = AIAgentService(api_key="test-key", client=client)  # type: ignore[arg-type]

    result = service.run("Hello")

    assert result.answer == "Answer"
    call = client.responses.calls[0]
    assert call["text_format"] is AgentOutput
    assert call["model"] == "test-model"
    assert "Hello" in call["input"]


def test_service_raises_on_missing_parsed_output() -> None:
    client = _StubClient(_StubResponse(None))
    service = AIAgentService(api_key="test-key", client=client)  # type: ignore[arg-type]

    with pytest.raises(AgentEmptyResponseError):
        service.run("Hello")


def test_service_raises_on_refusal() -> None:
    client = _StubClient(_StubResponse(None, refusal=True))
    service = AIAgentService(api_key="test-key", client=client)  # type: ignore[arg-type]

    with pytest.raises(AgentRefusalError):
        service.run("Hello")


def test_service_translates_provider_errors() -> None:
    from openai import APIConnectionError

    client = _StubClient(APIConnectionError(request=None))  # type: ignore[arg-type]
    service = AIAgentService(api_key="test-key", client=client)  # type: ignore[arg-type]

    with pytest.raises(AgentProviderError):
        service.run("Hello")
