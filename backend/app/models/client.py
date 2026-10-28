"""Tables of one client's own database.

They mirror ``ClientSnapshot`` so the deterministic engine runs unchanged on
data loaded from here. Money columns are exact decimals.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import ClientBase

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")
MoneyColumn = Numeric(14, 2, asdecimal=True)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Customer(ClientBase):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    as_of_date: Mapped[date | None] = mapped_column(Date)


class Account(ClientBase):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_type: Mapped[str] = mapped_column(String(32))
    iban: Mapped[str | None] = mapped_column(String(34))
    currency: Mapped[str] = mapped_column(String(3), default="RON")
    available_balance: Mapped[Decimal] = mapped_column(MoneyColumn)
    credit_limit: Mapped[Decimal | None] = mapped_column(MoneyColumn)
    accrued_interest: Mapped[Decimal | None] = mapped_column(MoneyColumn)


class Transaction(ClientBase):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"))
    booking_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(MoneyColumn)
    currency: Mapped[str] = mapped_column(String(3), default="RON")
    type: Mapped[str] = mapped_column(String(16))
    payment_method: Mapped[str] = mapped_column(String(32))
    merchant_name: Mapped[str] = mapped_column(String(128))
    mcc: Mapped[str | None] = mapped_column(String(4))
    category: Mapped[str | None] = mapped_column(String(64))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")


class ScheduledPayment(ClientBase):
    __tablename__ = "scheduled_payments"

    payment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Not a foreign key: a bill may be re-routed to another of the client's accounts.
    account_id: Mapped[str] = mapped_column(String(64))
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MoneyColumn)
    currency: Mapped[str] = mapped_column(String(3), default="RON")
    merchant_name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")


class ProductTerms(ClientBase):
    """Overdraft, savings and card terms: one row, stored as JSON."""

    __tablename__ = "product_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    terms: Mapped[dict[str, Any]] = mapped_column(JSONType)


class Analysis(ClientBase):
    """One analysis shown to the client: the engine's decision and its wording."""

    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    decision: Mapped[dict[str, Any]] = mapped_column(JSONType)
    recommendation: Mapped[dict[str, Any]] = mapped_column(JSONType)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
