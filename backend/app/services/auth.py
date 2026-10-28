"""Login against the directory database."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, issue_token, read_token, verify_password
from app.models.directory import User
from app.services.errors import InvalidCredentialsError, NotAuthenticatedError
from app.services.provisioning import seed_users

# Compared against when the username is unknown, so both failures take as long.
_DUMMY_HASH = hash_password("not-a-real-password")


def login(directory: Session, username: str, password: str) -> tuple[User, str]:
    user = directory.scalars(
        select(User).where(User.username == username.strip().lower())
    ).first()
    valid = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not valid:
        raise InvalidCredentialsError()
    return user, issue_token(user.id)


def user_for_token(directory: Session, token: str | None) -> User:
    user_id = read_token(token) if token else None
    user = directory.get(User, user_id) if user_id is not None else None
    if user is None:
        raise NotAuthenticatedError()
    return user


def demo_users(directory: Session) -> list[User]:
    """Users in the order of their seed files (one edge case after another)."""
    order = {seed.username: i for i, seed in enumerate(seed_users())}
    users = directory.scalars(select(User))
    return sorted(users, key=lambda u: (order.get(u.username, len(order)), u.username))
