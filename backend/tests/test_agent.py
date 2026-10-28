"""Agent endpoint and service tests (no network, no real credentials)."""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import DatabaseRouter
from app.models.client import Analysis
from app.schemas.banking import ClientSnapshot
from app.schemas.insights import BillDecision, RecommendationDraft
from app.services.ai_agent import TOOL_NAME, AIAgentService
from app.services.banking.engine import build_decision
from app.services.errors import (
    AgentConfigurationError,
    AgentEmptyResponseError,
    AgentProviderError,
    AgentRefusalError,
)
from tests.conftest import FakeClock

H = dict[str, str]

# --- Endpoints --------------------------------------------------------------


def test_dashboard_returns_engine_numbers(client: TestClient, andrei: H) -> None:
    response = client.get("/api/dashboard", headers=andrei)

    assert response.status_code == 200
    body = response.json()
    assert body["customer_name"] == "Andrei Popescu"
    assert body["projection"]["first_deficit_date"] == "2026-11-05"
    assert body["projection"]["peak_deficit"] == 318.4
    assert [(o["option_id"], o["cost"]) for o in body["options"]] == [
        ("credit_card", 0.0),
        ("savings", 12.4),
        ("overdraft", 31.19),
    ]
    assert body["balances"][0]["account_type"] == "CURRENT_ACCOUNT"


def test_analyze_uses_rules_without_ai_and_saves_analysis(
    client: TestClient, andrei: H, db_router: DatabaseRouter
) -> None:
    response = client.post("/api/agent/analyze", headers=andrei)

    assert response.status_code == 200
    body = response.json()
    recommendation = body["recommendation"]
    assert recommendation["generated_by"] == "rules"
    assert recommendation["fallback_reason"] == "AI provider not configured"
    assert recommendation["recommended_option_id"] == "credit_card"
    assert body["persisted"] is True

    with db_router.session("client_andrei") as session:
        stored = session.scalars(select(Analysis)).one()
    assert str(stored.id) == body["task_id"]
    with db_router.session("client_maria") as session:
        assert session.scalars(select(Analysis)).first() is None


def _verified_execute(
    client: TestClient, clock: FakeClock, headers: H, option_id: str
) -> Any:
    initiated = client.post(
        "/api/agent/execute/initiate", json={"option_id": option_id}, headers=headers
    )
    assert initiated.status_code == 201, initiated.text
    challenge_id = initiated.json()["challenge_id"]
    clock.advance(3)
    status = client.get(f"/api/agent/challenges/{challenge_id}", headers=headers)
    assert status.json()["status"] == "approved"
    return client.post(
        "/api/agent/execute", json={"challenge_id": challenge_id}, headers=headers
    )


def test_execute_then_analyze_reports_no_risk(
    client: TestClient, clock: FakeClock, andrei: H
) -> None:
    executed = _verified_execute(client, clock, andrei, "credit_card")
    assert executed.status_code == 200
    assert executed.json()["decision_after"]["no_action_needed"] is True

    analyzed = client.post("/api/agent/analyze", headers=andrei).json()
    assert analyzed["recommendation"]["status"] == "no_risk"


def test_execute_requires_approval(client: TestClient, andrei: H) -> None:
    initiated = client.post(
        "/api/agent/execute/initiate", json={"option_id": "credit_card"}, headers=andrei
    ).json()
    response = client.post(
        "/api/agent/execute",
        json={"challenge_id": initiated["challenge_id"]},
        headers=andrei,
    )

    assert response.status_code == 409
    assert (
        client.get("/api/dashboard", headers=andrei).json()["no_action_needed"] is False
    )


def test_cancel_challenge(client: TestClient, clock: FakeClock, andrei: H) -> None:
    challenge_id = client.post(
        "/api/agent/execute/initiate", json={"option_id": "credit_card"}, headers=andrei
    ).json()["challenge_id"]
    cancelled = client.post(
        f"/api/agent/challenges/{challenge_id}/cancel", headers=andrei
    )
    clock.advance(3)

    assert cancelled.json()["status"] == "cancelled"
    response = client.post(
        "/api/agent/execute", json={"challenge_id": challenge_id}, headers=andrei
    )
    assert response.status_code == 409


def test_unknown_challenge_is_404(client: TestClient, andrei: H) -> None:
    assert client.get("/api/agent/challenges/nope", headers=andrei).status_code == 404
    response = client.post(
        "/api/agent/execute", json={"challenge_id": "nope"}, headers=andrei
    )
    assert response.status_code == 404


def test_initiate_rejects_unknown_option(client: TestClient, andrei: H) -> None:
    response = client.post(
        "/api/agent/execute/initiate", json={"option_id": "lottery"}, headers=andrei
    )
    assert response.status_code == 422


def test_initiate_rejects_option_not_offered(
    client: TestClient, clock: FakeClock, andrei: H
) -> None:
    _verified_execute(client, clock, andrei, "credit_card")
    response = client.post(
        "/api/agent/execute/initiate", json={"option_id": "savings"}, headers=andrei
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "That option is not available for the current situation."
    )


def test_reset_restores_deficit(
    client: TestClient, clock: FakeClock, andrei: H
) -> None:
    _verified_execute(client, clock, andrei, "credit_card")
    response = client.post("/api/agent/reset", headers=andrei)

    assert response.status_code == 200
    assert response.json()["no_action_needed"] is False


# --- Service ----------------------------------------------------------------


def _tool_response(
    draft: dict[str, Any] | None, stop: str = "tool_use"
) -> dict[str, Any]:
    """A Bedrock Converse response, optionally carrying the recommendation tool call."""
    content: list[dict[str, Any]] = [{"text": "Here is the recommendation."}]
    if draft is not None:
        content.append(
            {"toolUse": {"toolUseId": "t1", "name": TOOL_NAME, "input": draft}}
        )
    return {
        "output": {"message": {"role": "assistant", "content": content}},
        "stopReason": stop,
    }


class _StubBedrock:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _service(
    response: dict[str, Any] | Exception,
) -> tuple[AIAgentService, _StubBedrock]:
    stub = _StubBedrock(response)
    return AIAgentService(client=stub), stub


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "Converse")


@pytest.fixture
def decision(snapshot: ClientSnapshot) -> BillDecision:
    return build_decision(snapshot)


def _draft(**overrides: Any) -> dict[str, Any]:
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
    return values


def test_service_uses_model_output_when_consistent(decision: BillDecision) -> None:
    service, stub = _service(_tool_response(_draft()))

    result = service.recommend(decision)

    assert result.generated_by == "llm"
    assert result.headline.startswith("Pay the Enel Energie bill")
    call = stub.calls[0]
    assert call["modelId"] == "test-model"
    tool = call["toolConfig"]["tools"][0]["toolSpec"]
    assert tool["name"] == TOOL_NAME
    assert tool["inputSchema"]["json"] == RecommendationDraft.model_json_schema()
    prompt = call["messages"][0]["content"][0]["text"]
    assert "Pre-computed decision" in prompt
    # Raw transactions never reach the model.
    assert "TXN-" not in prompt


def test_service_rejects_different_option(decision: BillDecision) -> None:
    service, _ = _service(_tool_response(_draft(recommended_option_id="savings")))

    result = service.recommend(decision)

    assert result.generated_by == "rules"
    assert result.recommended_option_id == "credit_card"
    assert "differs from the engine" in (result.fallback_reason or "")


def test_service_rejects_invented_amount(decision: BillDecision) -> None:
    service, _ = _service(_tool_response(_draft(reasons=["You would pay 999.99 RON."])))

    result = service.recommend(decision)

    assert result.generated_by == "rules"
    assert "999.99" in (result.fallback_reason or "")


def test_service_rejects_wrong_status(decision: BillDecision) -> None:
    service, _ = _service(_tool_response(_draft(status="no_risk")))
    assert service.recommend(decision).generated_by == "rules"


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (_tool_response(None, stop="end_turn"), AgentEmptyResponseError),
        (_tool_response({"headline": "missing fields"}), AgentEmptyResponseError),
        (_tool_response(None, stop="guardrail_intervened"), AgentRefusalError),
        (_client_error("ThrottlingException"), AgentProviderError),
        (_client_error("ExpiredTokenException"), AgentConfigurationError),
        (ReadTimeoutError(endpoint_url="https://bedrock"), AgentProviderError),
    ],
)
def test_service_draft_raises_and_recommend_falls_back(
    decision: BillDecision, response: Any, error: type[Exception]
) -> None:
    service, _ = _service(response)

    with pytest.raises(error):
        service.draft(decision)
    result = service.recommend(decision)
    assert result.generated_by == "rules"
    assert result.recommended_option_id == "credit_card"


def test_service_without_credentials_uses_rules(decision: BillDecision) -> None:
    with pytest.raises(AgentConfigurationError):
        AIAgentService().draft(decision)
    result = AIAgentService().recommend(decision)
    assert result.generated_by == "rules"
    assert result.fallback_reason == "AI provider not configured"
