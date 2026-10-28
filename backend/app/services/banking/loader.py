"""Load the demo client's data file into a validated ``ClientSnapshot``."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.banking import ClientSnapshot
from app.services.errors import BankingDataError

logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "client1_date.json"


def load_snapshot(path: Path | None = None) -> ClientSnapshot:
    """Read and validate the client data, resolving the "today" date.

    "Today" is ``DEMO_TODAY`` when set, otherwise the file's ``as_of_date``,
    otherwise the date of the latest transaction.
    """
    path = path or settings.demo_data_path or DEFAULT_DATA_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Client data file is not readable: %s", type(exc).__name__)
        raise BankingDataError() from exc

    try:
        snapshot = ClientSnapshot.model_validate_json(raw)
    except ValidationError as exc:
        logger.error("Client data file is invalid (%d errors)", exc.error_count())
        raise BankingDataError() from exc

    if snapshot.current_account() is None:
        logger.error("Client data has no current account")
        raise BankingDataError()

    if settings.demo_today is not None:
        snapshot.as_of_date = settings.demo_today
    elif snapshot.as_of_date is None:
        if not snapshot.transactions:
            raise BankingDataError()
        snapshot.as_of_date = max(t.booking_date for t in snapshot.transactions).date()

    return snapshot
