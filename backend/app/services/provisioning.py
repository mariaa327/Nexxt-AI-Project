"""Create, seed and reset the directory database and one database per user.

Seed files live in ``app/data/users/<username>.json``: the client data plus a
``user`` block (display name, demo password, caption). Provisioning is
idempotent: existing databases and data are left alone unless reset.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.database import ClientBase, DatabaseRouter, DirectoryBase
from app.core.security import hash_password
from app.models.directory import User
from app.services import client_repository
from app.services.banking.loader import load_snapshot, seed_files
from app.services.errors import BankingDataError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedUser:
    username: str
    display_name: str
    caption: str
    password: str
    path: Path
    position: int

    @property
    def database_name(self) -> str:
        return f"client_{self.username}"


def seed_users() -> list[SeedUser]:
    users = []
    for path in seed_files():
        meta = json.loads(path.read_text(encoding="utf-8")).get("user") or {}
        users.append(
            SeedUser(
                username=meta.get("username") or path.stem,
                display_name=meta.get("display_name") or path.stem.title(),
                caption=meta.get("caption") or "",
                password=meta["password"],
                path=path,
                position=int(meta.get("position") or 99),
            )
        )
    return sorted(users, key=lambda u: (u.position, u.username))


def _seed_for(username: str) -> SeedUser:
    seed = next((u for u in seed_users() if u.username == username), None)
    if seed is None:
        raise BankingDataError()
    return seed


def provision(router: DatabaseRouter, reset: bool = False) -> list[str]:
    """Make sure every seed user exists with their own seeded database."""
    router.ensure_database(settings.directory_database)
    DirectoryBase.metadata.create_all(router.engine(settings.directory_database))

    created = []
    for seed in seed_users():
        if router.ensure_database(seed.database_name):
            created.append(seed.database_name)
        ClientBase.metadata.create_all(router.engine(seed.database_name))
        with router.session(seed.database_name) as session:
            if reset or client_repository.is_empty(session):
                client_repository.write_seed(session, load_snapshot(seed.path))

        with router.directory_session() as directory:
            user = directory.scalars(
                select(User).where(User.username == seed.username)
            ).first()
            if user is None:
                directory.add(
                    User(
                        username=seed.username,
                        display_name=seed.display_name,
                        caption=seed.caption,
                        password_hash=hash_password(seed.password),
                        database_name=seed.database_name,
                    )
                )
            else:
                user.display_name, user.caption = seed.display_name, seed.caption
                if reset:
                    user.password_hash = hash_password(seed.password)
            directory.commit()
    logger.info(
        "Provisioned %d users (%d new databases)", len(seed_users()), len(created)
    )
    return created


def reset_client(router: DatabaseRouter, user: User) -> None:
    """Restore one user's database to their seed file."""
    seed = _seed_for(user.username)
    with router.session(user.database_name) as session:
        client_repository.write_seed(session, load_snapshot(seed.path))
