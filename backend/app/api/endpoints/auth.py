"""Login endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_directory
from app.schemas.auth import DemoUser, LoginRequest, LoginResponse, UserInfo
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in with username and password",
    responses={401: {"description": "Incorrect username or password"}},
)
def login(
    payload: LoginRequest, directory: Annotated[Session, Depends(get_directory)]
) -> LoginResponse:
    user, token = auth.login(directory, payload.username, payload.password)
    return LoginResponse(token=token, user=UserInfo.model_validate(user))


@router.get("/me", response_model=UserInfo, summary="The logged-in user")
def me(user: CurrentUser) -> UserInfo:
    return UserInfo.model_validate(user)


@router.get(
    "/demo-users",
    response_model=list[DemoUser],
    summary="Fictional demo accounts, for the login page",
)
def demo_users(directory: Annotated[Session, Depends(get_directory)]) -> list[DemoUser]:
    return [DemoUser.model_validate(u) for u in auth.demo_users(directory)]
