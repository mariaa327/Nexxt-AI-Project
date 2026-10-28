"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness and configuration summary")
def health() -> dict[str, object]:
    """Report that the API is running.

    Deliberately does not contact Supabase or the AI provider: this endpoint
    must work with no credentials configured.
    """
    return {
        "status": "ok",
        "service": "ai-hackathon-backend",
        "environment": settings.app_env,
        # Booleans only — never expose the values themselves.
        "integrations": {
            "database_configured": bool(settings.database_url),
            "supabase_auth_configured": bool(settings.resolved_jwks_url),
            "ai_configured": bool(settings.openai_api_key),
        },
    }
