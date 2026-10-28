"""Dependency providers, kept here so tests can override them."""

from __future__ import annotations

from app.services.ai_agent import AIAgentService
from app.services.banking.executor import DemoState, demo_state


def get_demo_state() -> DemoState:
    return demo_state


def get_agent_service() -> AIAgentService:
    return AIAgentService()
