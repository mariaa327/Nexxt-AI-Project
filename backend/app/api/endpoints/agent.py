"""Agent endpoints: analyse the situation, execute an option, reset the demo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_agent_service, get_demo_state
from app.core.database import maybe_get_db
from app.schemas.insights import (
    AnalyzeResponse,
    BillDecision,
    ExecuteRequest,
    ExecuteResponse,
)
from app.services.ai_agent import AIAgentService
from app.services.banking.engine import build_decision
from app.services.banking.executor import DemoState
from app.services.persistence import save_analysis

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Compute the decision and phrase the recommendation",
)
def analyze(
    state: Annotated[DemoState, Depends(get_demo_state)],
    agent: Annotated[AIAgentService, Depends(get_agent_service)],
    db: Annotated[Session | None, Depends(maybe_get_db)],
) -> AnalyzeResponse:
    snapshot = state.snapshot()
    decision = build_decision(snapshot)
    recommendation = agent.recommend(decision)
    task_id = save_analysis(db, snapshot.customer.customer_id, decision, recommendation)
    return AnalyzeResponse(
        decision=decision,
        recommendation=recommendation,
        task_id=task_id,
        persisted=task_id is not None,
    )


@router.post(
    "/execute",
    response_model=ExecuteResponse,
    summary="Apply an option to the demo client (simulated)",
    responses={422: {"description": "Option not available"}},
)
def execute(
    payload: ExecuteRequest,
    state: Annotated[DemoState, Depends(get_demo_state)],
) -> ExecuteResponse:
    return state.execute(payload.option_id)


@router.post(
    "/reset",
    response_model=BillDecision,
    summary="Reload the demo client's original data",
)
def reset(state: Annotated[DemoState, Depends(get_demo_state)]) -> BillDecision:
    state.reset()
    return build_decision(state.snapshot())
