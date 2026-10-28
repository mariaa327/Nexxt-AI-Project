"""Pydantic models for the client data file (accounts, transactions, products).

Amounts are parsed into ``Decimal`` from their string form so that a JSON
float such as ``182.3`` becomes exactly ``Decimal("182.3")``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

CENT = Decimal("0.01")


def _to_decimal(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    return value


def round_money(value: Decimal) -> Decimal:
    """Round to cents. Call once, at the end of a calculation."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


# Exact decimal in Python; a 2-decimal JSON number on the wire.
Money = Annotated[
    Decimal,
    BeforeValidator(_to_decimal),
    PlainSerializer(
        lambda v: float(round_money(v)), return_type=float, when_used="json"
    ),
]
# Interest rates keep their full precision.
Rate = Annotated[
    Decimal,
    BeforeValidator(_to_decimal),
    PlainSerializer(float, return_type=float, when_used="json"),
]


class Customer(BaseModel):
    customer_id: str
    first_name: str
    last_name: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class _AccountBase(BaseModel):
    account_id: str
    iban: str | None = None
    currency: str = "RON"
    available_balance: Money


class CurrentAccount(_AccountBase):
    account_type: Literal["CURRENT_ACCOUNT"]


class CreditCardAccount(_AccountBase):
    account_type: Literal["CREDIT_CARD"]
    credit_limit: Money


class SavingsAccount(_AccountBase):
    account_type: Literal["SAVINGS_ACCOUNT"]
    accrued_interest: Money = Decimal(0)


Account = Annotated[
    CurrentAccount | CreditCardAccount | SavingsAccount,
    Field(discriminator="account_type"),
]


class Transaction(BaseModel):
    transaction_id: str
    account_id: str
    booking_date: datetime
    amount: Money
    currency: str = "RON"
    type: str
    payment_method: str
    merchant_name: str
    mcc: str | None = None
    category: str | None = None
    is_recurring: bool = False
    description: str = ""


class ScheduledPayment(BaseModel):
    """A known future movement on an account (bill, direct debit or salary)."""

    payment_id: str
    account_id: str
    due_date: date
    amount: Money
    currency: str = "RON"
    merchant_name: str
    category: str | None = None
    description: str = ""


class OverdraftTerms(BaseModel):
    daily_interest_rate: Rate
    flat_fee: Money


class SavingsTerms(BaseModel):
    annual_interest_rate: Rate
    early_withdrawal_forfeits_interest: bool = True


class CreditCardTerms(BaseModel):
    annual_interest_rate: Rate
    grace_period_days: int = Field(ge=0)


class ProductParameters(BaseModel):
    overdraft: OverdraftTerms
    savings: SavingsTerms
    credit_card: CreditCardTerms


class ClientSnapshot(BaseModel):
    """Everything the engine knows about one client at one point in time."""

    as_of_date: date | None = None
    customer: Customer
    accounts: list[Account]
    product_parameters: ProductParameters
    scheduled_payments: list[ScheduledPayment] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)

    def current_account(self) -> CurrentAccount | None:
        return next((a for a in self.accounts if isinstance(a, CurrentAccount)), None)

    def credit_card(self) -> CreditCardAccount | None:
        return next(
            (a for a in self.accounts if isinstance(a, CreditCardAccount)), None
        )

    def savings_account(self) -> SavingsAccount | None:
        return next((a for a in self.accounts if isinstance(a, SavingsAccount)), None)
