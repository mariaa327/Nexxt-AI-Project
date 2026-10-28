"""Agent endpoint and service tests (no network, no real credentials)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_agent_service, get_demo_state
from app.core.database import maybe_get_db
from app.main import app
from app.models.domain import AgentTask
from app.schemas.banking import ClientSnapshot
from app.schemas.insights import BillDecision, RecommendationDraft
from app.services.ai_agent import AIAgentService
from app.services.banking.engine import build_decision
from app.services.banking.executor import DemoState
from app.services.errors import (
    AgentConfigurationError,
    AgentEmptyResponseError,
    AgentProviderError,
    AgentRefusalError,
)

# --- Endpoints --------------------------------------------------------------


def test_dashboard_returns_engine_numbers(client: TestClient) -> None:
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["projection"]["first_deficit_date"] == "2026-11-05"
    assert body["projection"]["peak_deficit"] == 318.4
    assert [(o["option_id"], o["cost"]) for o in body["options"]] == [
        ("credit_card", 0.0),
        ("savings", 12.4),
        ("overdraft", 31.19),
    ]


def test_analyze_without_ai_key_uses_rules_and_persists(
    client: TestClient, db_session: Session
) -> None:
    response = client.post("/api/agent/analyze")

    assert response.status_code == 200
    body = response.json()
    recommendation = body["recommendation"]
    assert recommendation["generated_by"] == "rules"
    assert recommendation["fallback_reason"] == "AI provider not configured"
    assert recommendation["recommended_option_id"] == "credit_card"
    assert recommendation["reasons"]
    assert body["persisted"] is True

    task = db_session.query(AgentTask).one()
    assert task.customer_id == "CUST-883921"
    assert str(task.id) == body["task_id"]


def test_analyze_without_database_still_succeeds(state: DemoState) -> None:
    def no_db() -> Generator[None, None, None]:
        yield None

    app.dependency_overrides[maybe_get_db] = no_db
    app.dependency_overrides[get_demo_state] = lambda: state
    app.dependency_overrides[get_agent_service] = lambda: AIAgentService(api_key=None)
    try:
        with TestClient(app) as client:
            response = client.post("/api/agent/analyze")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["persisted"] is False
    assert response.json()["task_id"] is None


def test_execute_then_analyze_reports_no_risk(client: TestClient) -> None:
    executed = client.post("/api/agent/execute", json={"option_id": "credit_card"})
    assert executed.status_code == 200
    assert executed.json()["decision_after"]["no_action_needed"] is True

    analyzed = client.post("/api/agent/analyze").json()
    assert analyzed["recommendation"]["status"] == "no_risk"


def test_execute_rejects_unknown_option(client: TestClient) -> None:
    response = client.post("/api/agent/execute", json={"option_id": "lottery"})
    assert response.status_code == 422


def test_execute_rejects_option_not_offered(client: TestClient) -> None:
    client.post("/api/agent/execute", json={"option_id": "credit_card"})
    response = client.post("/api/agent/execute", json={"option_id": "savings"})

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "That option is not available for the current situation."
    )


def test_reset_restores_deficit(client: TestClient) -> None:
    client.post("/api/agent/execute", json={"option_id": "credit_card"})
    response = client.post("/api/agent/reset")

    assert response.status_code == 200
    assert response.json()["no_action_needed"] is False


# --- Service ----------------------------------------------------------------


class _StubResponse:
    def __init__(
        self,
        parsed: RecommendationDraft | None,
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


def _service(response: _StubResponse | Exception) -> tuple[AIAgentService, _StubClient]:
    stub = _StubClient(response)
    return AIAgentService(api_key="test-key", client=stub), stub  # type: ignore[arg-type]


@pytest.fixture
def decision(snapshot: ClientSnapshot) -> BillDecision:
    return build_decision(snapshot)


def _draft(**overrides: Any) -> RecommendationDraft:
    values: dict[str, Any] = {
        "status": "action_required",
        "recommended_option_id": "credit_card",
        "headline": "Pay the Enel Energie bill of 618.40 RON with your credit card.",
        "reasons": [
            "Your account would go negative on 5 November, down to -318.40 RON.",
            "Doing nothing would cost 31.19 RON.",
        ],
        "trade_offs": ["Withdraw from savings: 12.40 RON in forfeited interest."],
    }
    values.update(overrides)
    return RecommendationDraft(**values)


def test_service_uses_model_output_when_consistent(decision: BillDecision) -> None:
    service, stub = _service(_StubResponse(_draft()))

    result = service.recommend(decision)

    assert result.generated_by == "llm"
    assert result.headline.startswith("Pay the Enel Energie bill")
    call = stub.responses.calls[0]
    assert call["text_format"] is RecommendationDraft
    assert call["model"] == "test-model"
    assert "Pre-computed decision" in call["input"]
    # Raw transactions never reach the model.
    assert "TXN-" not in call["input"]


def test_service_rejects_different_option(decision: BillDecision) -> None:
    service, _ = _service(_StubResponse(_draft(recommended_option_id="savings")))

    result = service.recommend(decision)

    assert result.generated_by == "rules"
    assert result.recommended_option_id == "credit_card"
    assert "differs from the engine" in (result.fallback_reason or "")


def test_service_rejects_invented_amount(decision: BillDecision) -> None:
    service, _ = _service(_StubResponse(_draft(reasons=["You would pay 999.99 RON."])))

    result = service.recommend(decision)

    assert result.generated_by == "rules"
    assert "999.99" in (result.fallback_reason or "")


def test_service_rejects_wrong_status(decision: BillDecision) -> None:
    service, _ = _service(_StubResponse(_draft(status="no_risk")))
    assert service.recommend(decision).generated_by == "rules"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (_StubResponse(None), AgentEmptyResponseError),
        (_StubResponse(None, refusal=True), AgentRefusalError),
        (_StubResponse(None, status="failed"), AgentProviderError),
    ],
)
def test_service_draft_raises_and_recommend_falls_back(
    decision: BillDecision, response: _StubResponse, error: type[Exception]
) -> None:
    service, _ = _service(response)

    with pytest.raises(error):
        service.draft(decision)
    assert service.recommend(decision).generated_by == "rules"


def test_service_translates_provider_errors(decision: BillDecision) -> None:
    from openai import APIConnectionError

    service, _ = _service(APIConnectionError(request=None))  # type: ignore[arg-type]

    with pytest.raises(AgentProviderError):
        service.draft(decision)
    result = service.recommend(decision)
    assert result.generated_by == "rules"
    assert "sk-" not in (result.fallback_reason or "")


def test_service_requires_api_key_for_draft(decision: BillDecision) -> None:
    with pytest.raises(AgentConfigurationError):
        AIAgentService(api_key=None).draft(decision)
