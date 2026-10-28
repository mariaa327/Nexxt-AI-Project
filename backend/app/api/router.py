"""Aggregated API router mounted under ``/api``."""

from fastapi import APIRouter

from app.api.endpoints import agent, auth, dashboard, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(agent.router)

__all__ = ["api_router"]
