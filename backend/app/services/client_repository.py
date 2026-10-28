"""Read and write one client's database as a ``ClientSnapshot``.

The engine only ever sees snapshots; this module is the only place that maps
them to and from the client's tables.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import client as m
from app.schemas.banking import (
    ClientSnapshot,
    CreditCardAccount,
    SavingsAccount,
)
from app.schemas.insights import AgentRecommendation, BillDecision
from app.services.errors import BankingDataError

# Current account first: it is the one the dashboard is about.
ACCOUNT_ORDER = {"CURRENT_ACCOUNT": 0, "CREDIT_CARD": 1, "SAVINGS_ACCOUNT": 2}
_TABLES = (
    m.Analysis,
    m.ScheduledPayment,
    m.Transaction,
    m.Account,
    m.ProductTerms,
    m.Customer,
)


def load_snapshot(session: Session) -> ClientSnapshot:
    customer = session.scalars(select(m.Customer)).first()
    terms = session.scalars(select(m.ProductTerms)).first()
    if customer is None or terms is None:
        raise BankingDataError()

    accounts = []
    rows = sorted(
        session.scalars(select(m.Account)),
        key=lambda a: (ACCOUNT_ORDER.get(a.account_type, 9), a.account_id),
    )
    for a in rows:
        item: dict[str, object] = {
            "account_id": a.account_id,
            "account_type": a.account_type,
            "iban": a.iban,
            "currency": a.currency,
            "available_balance": a.available_balance,
        }
        if a.account_type == "CREDIT_CARD":
            item["credit_limit"] = a.credit_limit
        if a.account_type == "SAVINGS_ACCOUNT":
            item["accrued_interest"] = a.accrued_interest
        accounts.append(item)

    transactions = [
        {c: getattr(t, c) for c in _columns(m.Transaction)}
        for t in session.scalars(
            select(m.Transaction).order_by(m.Transaction.booking_date)
        )
    ]
    payments = [
        {c: getattr(p, c) for c in _columns(m.ScheduledPayment)}
        for p in session.scalars(
            select(m.ScheduledPayment).order_by(m.ScheduledPayment.due_date)
        )
    ]
    return ClientSnapshot.model_validate(
        {
            "as_of_date": customer.as_of_date,
            "customer": {
                "customer_id": customer.customer_id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
            },
            "accounts": accounts,
            "product_parameters": terms.terms,
            "scheduled_payments": payments,
            "transactions": transactions,
        }
    )


def _columns(model: type[m.ClientBase]) -> list[str]:
    return [c.key for c in model.__table__.columns]


def is_empty(session: Session) -> bool:
    return session.scalars(select(m.Customer)).first() is None


def write_seed(session: Session, snapshot: ClientSnapshot) -> None:
    """Replace everything in the client's database with ``snapshot``."""
    for table in _TABLES:
        session.execute(delete(table))
    session.add(
        m.Customer(
            customer_id=snapshot.customer.customer_id,
            first_name=snapshot.customer.first_name,
            last_name=snapshot.customer.last_name,
            as_of_date=snapshot.as_of_date,
        )
    )
    session.add(
        m.ProductTerms(id=1, terms=snapshot.product_parameters.model_dump(mode="json"))
    )
    for a in snapshot.accounts:
        session.add(
            m.Account(
                account_id=a.account_id,
                account_type=a.account_type,
                iban=a.iban,
                currency=a.currency,
                available_balance=a.available_balance,
                credit_limit=a.credit_limit
                if isinstance(a, CreditCardAccount)
                else None,
                accrued_interest=a.accrued_interest
                if isinstance(a, SavingsAccount)
                else None,
            )
        )
    session.flush()
    for t in snapshot.transactions:
        session.add(m.Transaction(**t.model_dump()))
    for p in snapshot.scheduled_payments:
        session.add(m.ScheduledPayment(**p.model_dump()))
    session.commit()


def save_changes(session: Session, after: ClientSnapshot) -> None:
    """Persist what executing an option changes: balances, accrued interest and
    which account pays each scheduled payment. One transaction."""
    for a in after.accounts:
        row = session.get(m.Account, a.account_id)
        if row is None:
            raise BankingDataError()
        row.available_balance = a.available_balance
        if isinstance(a, SavingsAccount):
            row.accrued_interest = a.accrued_interest
    existing = {p.payment_id: p for p in session.scalars(select(m.ScheduledPayment))}
    for p in after.scheduled_payments:
        row = existing.get(p.payment_id)
        if row is None:
            # Payments inferred from history become explicit once re-routed.
            session.add(m.ScheduledPayment(**p.model_dump()))
        else:
            row.account_id = p.account_id
    session.commit()


def save_analysis(
    session: Session, decision: BillDecision, recommendation: AgentRecommendation
) -> m.Analysis:
    analysis = m.Analysis(
        decision=decision.model_dump(mode="json"),
        recommendation=recommendation.model_dump(mode="json"),
    )
    session.add(analysis)
    session.commit()
    return analysis
