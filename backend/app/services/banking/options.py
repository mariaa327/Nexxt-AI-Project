"""Price every way of covering a projected deficit, then rank them.

Each option is priced as if it were the only action taken. Amounts are summed
unrounded and rounded once at the end (rounding per day shifts the total).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.schemas.banking import ClientSnapshot, round_money
from app.schemas.insights import CostOption, Projection, UpcomingPayment
from app.services.banking.projection import project_balance

# Tie-break when two options cost the same: keep savings and avoid overdraft.
PREFERENCE: tuple[str, ...] = ("credit_card", "savings", "overdraft")
DAYS_PER_YEAR = Decimal(365)


def ron(value: Decimal) -> str:
    """Format an amount for people: ``1,234.50 RON``."""
    return f"{round_money(value):,.2f} RON"


def day_label(value: date) -> str:
    return f"{value.day} {value:%B}"


def triggering_payment(
    projection: Projection, payments: list[UpcomingPayment]
) -> UpcomingPayment | None:
    """The largest debit on the day the balance first goes negative."""
    if projection.first_deficit_date is None:
        return None
    debits = [
        p
        for p in payments
        if p.due_date == projection.first_deficit_date and p.amount < 0
    ]
    return min(debits, key=lambda p: p.amount, default=None)


def _overdraft(snapshot: ClientSnapshot, projection: Projection) -> CostOption:
    terms = snapshot.product_parameters.overdraft
    interest = projection.deficit_exposure * terms.daily_interest_rate
    cost = round_money(terms.flat_fee + interest)
    return CostOption(
        option_id="overdraft",
        label="Do nothing (overdraft)",
        action="Let the current account go negative until the next income arrives.",
        amount=projection.peak_deficit,
        cost=cost,
        formula=(
            f"{terms.flat_fee:.2f} fee + {projection.deficit_exposure:.2f} "
            f"(sum of daily negative balances) × {terms.daily_interest_rate} daily rate "
            f"= {cost:.2f}"
        ),
        explanation=(
            f"An overdraft fee of {ron(terms.flat_fee)} plus {ron(interest)} interest "
            f"for {projection.deficit_days} days below zero."
        ),
        assumptions=[
            "Interest accrues daily on the end-of-day negative balance.",
            "The fee is charged once per overdraft episode.",
        ],
        prevents_overdraft=False,
        feasible=True,
    )


def _savings(
    snapshot: ClientSnapshot,
    projection: Projection,
    opening: Decimal,
    as_of: date,
    payments: list[UpcomingPayment],
) -> CostOption | None:
    account = snapshot.savings_account()
    if account is None:
        return None
    terms = snapshot.product_parameters.savings
    amount = projection.peak_deficit
    forfeited = (
        account.accrued_interest
        if terms.early_withdrawal_forfeits_interest
        else Decimal(0)
    )
    cost = round_money(forfeited)
    feasible = account.available_balance >= amount
    after = project_balance(opening + amount, as_of, payments)
    deadline = projection.first_deficit_date or as_of
    return CostOption(
        option_id="savings",
        label="Withdraw from savings",
        action=f"Move {ron(amount)} from savings to the current account before {day_label(deadline)}.",
        amount=amount,
        cost=cost,
        formula=f"accrued interest forfeited = {cost:.2f}",
        explanation=(
            f"Breaking the savings deposit early forfeits the {ron(forfeited)} of interest "
            "accrued so far."
        ),
        assumptions=[
            f"The transfer is made today ({as_of.isoformat()}).",
            "Interest the withdrawn amount would have earned later is not counted.",
        ],
        prevents_overdraft=feasible and after.first_deficit_date is None,
        feasible=feasible,
        source_account_id=account.account_id,
    )


def _credit_card(
    snapshot: ClientSnapshot,
    projection: Projection,
    opening: Decimal,
    as_of: date,
    payments: list[UpcomingPayment],
    trigger: UpcomingPayment | None,
) -> CostOption | None:
    card = snapshot.credit_card()
    if card is None or trigger is None:
        return None
    terms = snapshot.product_parameters.credit_card
    amount = -trigger.amount
    feasible = card.available_balance >= amount
    remaining = [p for p in payments if p.payment_id != trigger.payment_id]
    after = project_balance(opening, as_of, remaining)

    repay_date = projection.next_income_date
    assumptions = ["No earlier card balance is carried past its own grace period."]
    if repay_date is None:
        days = None
        interest = Decimal(0)
        assumptions.append("The card is repaid within the grace period.")
        timing = f"repaid within {terms.grace_period_days} days"
    else:
        days = (repay_date - trigger.due_date).days
        interest = (
            Decimal(0)
            if days <= terms.grace_period_days
            else amount * terms.annual_interest_rate / DAYS_PER_YEAR * days
        )
        assumptions.append(
            f"The card is repaid from the income on {repay_date.isoformat()}."
        )
        timing = f"repaid after {days} days"
    cost = round_money(interest)

    if interest == 0:
        explanation = (
            f"Repaid from your income {days} days later, inside the "
            f"{terms.grace_period_days}-day interest-free period."
            if days is not None
            else f"Repaid inside the {terms.grace_period_days}-day interest-free period."
        )
    else:
        explanation = (
            f"Repaid after {days} days, beyond the {terms.grace_period_days}-day "
            f"interest-free period, so {ron(interest)} of card interest applies."
        )

    return CostOption(
        option_id="credit_card",
        label="Pay the bill with the credit card",
        action=(
            f"Pay {trigger.merchant_name} ({ron(amount)}, due {day_label(trigger.due_date)}) "
            "from the credit card instead of the current account."
        ),
        amount=amount,
        cost=cost,
        formula=f"{timing}, grace period {terms.grace_period_days} days → interest {cost:.2f}",
        explanation=explanation,
        assumptions=assumptions,
        prevents_overdraft=feasible and after.first_deficit_date is None,
        feasible=feasible,
        source_account_id=card.account_id,
    )


def rank(options: list[CostOption]) -> list[CostOption]:
    """Feasible first, then cheapest, then by preference."""
    return sorted(
        options,
        key=lambda o: (not o.feasible, o.cost, PREFERENCE.index(o.option_id)),
    )


def price_options(
    snapshot: ClientSnapshot,
    projection: Projection,
    payments: list[UpcomingPayment],
    trigger: UpcomingPayment | None,
) -> list[CostOption]:
    """All coverage options for the deficit, cheapest first; empty when none."""
    if projection.first_deficit_date is None:
        return []
    current = snapshot.current_account()
    assert current is not None and snapshot.as_of_date is not None
    opening, as_of = current.available_balance, snapshot.as_of_date

    candidates = [
        _overdraft(snapshot, projection),
        _savings(snapshot, projection, opening, as_of, payments),
        _credit_card(snapshot, projection, opening, as_of, payments, trigger),
    ]
    return rank([o for o in candidates if o is not None])
