"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.services.banking.loader import load_snapshot
from app.services.errors import BankingDataError

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness and configuration summary")
def health() -> dict[str, object]:
    """Report that the API is running.

    Deliberately does not contact the database or the AI provider: this
    endpoint must work with no credentials configured.
    """
    try:
        load_snapshot()
        demo_data_loaded = True
    except BankingDataError:
        demo_data_loaded = False

    return {
        "status": "ok",
        "service": "overdraft-agent-backend",
        "environment": settings.app_env,
        # Booleans only — never expose the values themselves.
        "integrations": {
            "database_configured": bool(settings.database_url),
            "ai_configured": bool(settings.openai_api_key),
            "demo_data_loaded": demo_data_loaded,
        },
    }
