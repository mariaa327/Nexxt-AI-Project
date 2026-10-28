"""Build the ``BillDecision`` for a client snapshot."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.banking import (
    ClientSnapshot,
    CreditCardAccount,
    SavingsAccount,
)
from app.schemas.insights import AccountBalance, BillDecision, UpcomingPayment
from app.services.banking.categorizer import summarize
from app.services.banking.options import price_options, triggering_payment
from app.services.banking.projection import project_balance
from app.services.banking.recurring import detect_recurring

ACCOUNT_LABELS = {
    "CURRENT_ACCOUNT": "Current account",
    "CREDIT_CARD": "Credit card",
    "SAVINGS_ACCOUNT": "Savings account",
}


def account_balances(snapshot: ClientSnapshot) -> list[AccountBalance]:
    return [
        AccountBalance(
            account_id=a.account_id,
            account_type=a.account_type,
            label=ACCOUNT_LABELS[a.account_type],
            balance=a.available_balance,
            credit_limit=a.credit_limit if isinstance(a, CreditCardAccount) else None,
            accrued_interest=a.accrued_interest
            if isinstance(a, SavingsAccount)
            else None,
        )
        for a in snapshot.accounts
    ]


def build_decision(snapshot: ClientSnapshot) -> BillDecision:
    current = snapshot.current_account()
    as_of = snapshot.as_of_date
    assert current is not None and as_of is not None, "validated by the loader"

    recurring = detect_recurring(snapshot.transactions, as_of)

    # Known scheduled payments win; otherwise next month is inferred from history.
    if snapshot.scheduled_payments:
        source = "scheduled"
        payments = [
            UpcomingPayment(
                payment_id=p.payment_id,
                account_id=p.account_id,
                due_date=p.due_date,
                amount=p.amount,
                merchant_name=p.merchant_name,
                category=p.category,
                description=p.description,
            )
            for p in snapshot.scheduled_payments
        ]
    else:
        source = "recurring_history"
        payments = [
            UpcomingPayment(
                payment_id=f"REC-{o.account_id}-{o.merchant_name}",
                account_id=o.account_id,
                due_date=o.next_due_date,
                amount=o.amount,
                merchant_name=o.merchant_name,
                category=o.category,
                description="Expected from recurring history",
            )
            for o in recurring
        ]
    payments = sorted(
        (
            p
            for p in payments
            if p.account_id == current.account_id and p.due_date > as_of
        ),
        key=lambda p: (p.due_date, p.amount < 0),
    )

    projection = project_balance(current.available_balance, as_of, payments)
    trigger = triggering_payment(projection, payments)
    options = price_options(snapshot, projection, payments, trigger)
    recommended = options[0] if options else None
    overdraft = next((o for o in options if o.option_id == "overdraft"), None)

    return BillDecision(
        customer_name=snapshot.customer.full_name,
        as_of_date=as_of,
        payments_source=source,
        balances=account_balances(snapshot),
        situation=summarize(snapshot.transactions, recurring),
        upcoming_payments=[p for p in payments if p.due_date <= projection.horizon_end],
        projection=projection,
        no_action_needed=projection.first_deficit_date is None,
        triggering_payment=trigger,
        options=options,
        recommended_option_id=recommended.option_id if recommended else None,
        saving_vs_doing_nothing=(
            overdraft.cost - recommended.cost
            if overdraft and recommended
            else Decimal(0)
        ),
    )
