"""Login request and response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    display_name: str


class DemoUser(UserInfo):
    caption: str


class LoginResponse(BaseModel):
    token: str
    user: UserInfo
