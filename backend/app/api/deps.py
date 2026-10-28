"""Dependency providers, kept here so tests can override them."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import DatabaseRouter, get_router
from app.models.directory import User
from app.services.ai_agent import AIAgentService
from app.services.auth import user_for_token
from app.services.banking.executor import ChallengeStore, challenge_store

bearer = HTTPBearer(auto_error=False)


def get_challenge_store() -> ChallengeStore:
    return challenge_store


def get_agent_service() -> AIAgentService:
    return AIAgentService()


def get_directory(
    router: Annotated[DatabaseRouter, Depends(get_router)],
) -> Generator[Session, None, None]:
    with router.directory_session() as session:
        yield session


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    directory: Annotated[Session, Depends(get_directory)],
) -> User:
    token = credentials.credentials if credentials else None
    return user_for_token(directory, token)


def get_client_session(
    user: Annotated[User, Depends(get_current_user)],
    router: Annotated[DatabaseRouter, Depends(get_router)],
) -> Generator[Session, None, None]:
    """A session on the logged-in user's own database, and no other."""
    with router.session(user.database_name) as session:
        yield session


CurrentUser = Annotated[User, Depends(get_current_user)]
ClientSession = Annotated[Session, Depends(get_client_session)]
