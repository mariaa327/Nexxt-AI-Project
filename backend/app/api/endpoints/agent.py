"""Agent endpoints for the logged-in user: analyse, verify, execute, reset."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    ClientSession,
    CurrentUser,
    get_agent_service,
    get_challenge_store,
)
from app.core.database import DatabaseRouter, get_router
from app.schemas.insights import (
    AnalyzeResponse,
    BillDecision,
    Challenge,
    ExecuteRequest,
    ExecuteResponse,
    InitiateRequest,
)
from app.services import client_repository
from app.services.ai_agent import AIAgentService
from app.services.banking.engine import build_decision
from app.services.banking.executor import ChallengeStore, apply_option
from app.services.provisioning import reset_client

router = APIRouter(
    prefix="/agent", tags=["agent"], responses={401: {"description": "Not logged in"}}
)
Store = Annotated[ChallengeStore, Depends(get_challenge_store)]


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Compute the decision and phrase the recommendation",
)
def analyze(
    session: ClientSession,
    agent: Annotated[AIAgentService, Depends(get_agent_service)],
) -> AnalyzeResponse:
    decision = build_decision(client_repository.load_snapshot(session))
    recommendation = agent.recommend(decision)
    analysis = client_repository.save_analysis(session, decision, recommendation)
    return AnalyzeResponse(
        decision=decision,
        recommendation=recommendation,
        task_id=analysis.id,
        persisted=True,
    )


@router.post(
    "/execute/initiate",
    response_model=Challenge,
    status_code=status.HTTP_201_CREATED,
    summary="Start payment verification (simulated banking-app approval)",
    responses={422: {"description": "Option not available"}},
)
def initiate_execution(
    payload: InitiateRequest, user: CurrentUser, session: ClientSession, store: Store
) -> Challenge:
    snapshot = client_repository.load_snapshot(session)
    return store.initiate(user.username, snapshot, payload.option_id)


@router.get(
    "/challenges/{challenge_id}",
    response_model=Challenge,
    summary="Verification status",
    responses={404: {"description": "Unknown verification request"}},
)
def get_challenge(challenge_id: str, user: CurrentUser, store: Store) -> Challenge:
    return store.challenge(user.username, challenge_id)


@router.post(
    "/challenges/{challenge_id}/cancel",
    response_model=Challenge,
    summary="Cancel a pending verification",
    responses={404: {"description": "Unknown verification request"}},
)
def cancel_challenge(challenge_id: str, user: CurrentUser, store: Store) -> Challenge:
    return store.cancel(user.username, challenge_id)


@router.post(
    "/execute",
    response_model=ExecuteResponse,
    summary="Apply a verified option and save it to the user's database (simulated)",
    responses={
        404: {"description": "Unknown verification request"},
        409: {"description": "Not approved yet, cancelled or already used"},
        410: {"description": "Verification expired"},
        422: {"description": "Option no longer available"},
    },
)
def execute(
    payload: ExecuteRequest, user: CurrentUser, session: ClientSession, store: Store
) -> ExecuteResponse:
    challenge = store.consume(user.username, payload.challenge_id)
    after, result = apply_option(
        client_repository.load_snapshot(session), challenge.option_id
    )
    client_repository.save_changes(session, after)
    return result


@router.post(
    "/reset",
    response_model=BillDecision,
    summary="Restore the logged-in user's original demo data",
)
def reset(
    user: CurrentUser,
    store: Store,
    db_router: Annotated[DatabaseRouter, Depends(get_router)],
) -> BillDecision:
    reset_client(db_router, user)
    store.clear(user.username)
    with db_router.session(user.database_name) as session:
        return build_decision(client_repository.load_snapshot(session))
