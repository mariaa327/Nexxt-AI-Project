"""Agent endpoint: run the AI agent and persist the result for the user."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.domain import AgentTask
from app.schemas.agent import AgentOutput, AgentRunRequest, AgentRunResponse
from app.services.ai_agent import AgentServiceError, AIAgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


def get_agent_service() -> AIAgentService:
    """Service provider kept as a dependency so tests can override it."""
    return AIAgentService()


@router.post(
    "/run",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run the AI agent for the authenticated user",
    responses={
        401: {"description": "Missing or invalid bearer token"},
        422: {"description": "Invalid prompt or model refusal"},
        500: {"description": "Server misconfiguration"},
        502: {"description": "AI provider error"},
        503: {"description": "Database or AI service unavailable"},
    },
)
def run_agent(
    payload: AgentRunRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    agent: Annotated[AIAgentService, Depends(get_agent_service)],
) -> AgentRunResponse:
    """Run the agent, store the task, and return the structured result."""
    try:
        result: AgentOutput = agent.run(payload.prompt)
    except AgentServiceError as exc:
        # Service exceptions carry safe, human-readable messages.
        raise HTTPException(
            status_code=exc.http_status, detail=exc.public_message
        ) from exc

    task = AgentTask(
        user_id=user.user_id,
        prompt=payload.prompt,
        result=result.model_dump(mode="json"),
    )

    try:
        db.add(task)
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Failed to persist agent task: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is unavailable. Please try again later.",
        ) from exc

    return AgentRunResponse(
        id=task.id,
        result=AgentOutput.model_validate(task.result),
        created_at=task.created_at,
    )


__all__ = ["get_agent_service", "router"]
