"""Health check endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import DatabaseRouter, get_router

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness and configuration summary")
def health(
    db_router: Annotated[DatabaseRouter, Depends(get_router)],
) -> dict[str, object]:
    """Report that the API is running. Never calls the AI provider, never fails."""
    try:
        with db_router.directory_session() as session:
            session.execute(text("SELECT 1"))
        database_reachable = True
    except (SQLAlchemyError, OSError):
        database_reachable = False

    return {
        "status": "ok",
        "service": "overdraft-agent-backend",
        "environment": settings.app_env,
        # Booleans only — never expose the values themselves.
        "integrations": {
            "database_reachable": database_reachable,
            "ai_configured": bool(settings.aws_access_key_id),
        },
    }
