"""Parse client data (the bundled seed files) into a ``ClientSnapshot``."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.banking import ClientSnapshot
from app.services.errors import BankingDataError, InvalidClientDataError

logger = logging.getLogger(__name__)

USERS_DIR = Path(__file__).resolve().parents[2] / "data" / "users"
DEFAULT_DATA_PATH = USERS_DIR / "andrei.json"

# Generous for a month of history; keeps a bad seed from tying up the engine.
MAX_TRANSACTIONS = 5000


def parse_snapshot(data: dict[str, Any]) -> ClientSnapshot:
    """Validate client data and resolve "today".

    "Today" is ``DEMO_TODAY`` when set, otherwise the data's ``as_of_date``,
    otherwise the date of the latest transaction. Raises
    ``InvalidClientDataError`` with a readable reason.
    """
    try:
        snapshot = ClientSnapshot.model_validate(data)
    except ValidationError as exc:
        reasons = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()[:3]
        ]
        raise InvalidClientDataError("; ".join(reasons)) from exc

    if snapshot.current_account() is None:
        raise InvalidClientDataError("accounts: a CURRENT_ACCOUNT is required")
    if len(snapshot.transactions) > MAX_TRANSACTIONS:
        raise InvalidClientDataError(
            f"transactions: at most {MAX_TRANSACTIONS} allowed"
        )

    if settings.demo_today is not None:
        snapshot.as_of_date = settings.demo_today
    elif snapshot.as_of_date is None:
        if not snapshot.transactions:
            raise InvalidClientDataError(
                "as_of_date is required when there are no transactions"
            )
        snapshot.as_of_date = max(t.booking_date for t in snapshot.transactions).date()
    return snapshot


def load_snapshot(path: Path | None = None) -> ClientSnapshot:
    """Read a bundled data file. A broken bundled file is a server error."""
    path = path or DEFAULT_DATA_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Client data file is not readable: %s", type(exc).__name__)
        raise BankingDataError() from exc
    try:
        return parse_snapshot(data)
    except InvalidClientDataError as exc:
        logger.error(
            "Client data file %s is invalid: %s", path.name, exc.public_message
        )
        raise BankingDataError() from exc


def seed_files() -> list[Path]:
    """One seed file per fictional user."""
    return sorted(USERS_DIR.glob("*.json"))
