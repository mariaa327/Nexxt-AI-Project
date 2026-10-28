"""Detect recurring obligations (bills, subscriptions, salary) in the history."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.schemas.banking import Transaction
from app.schemas.insights import RecurringObligation
from app.services.banking.categorizer import categorize, is_internal_transfer

# Amounts within 5% of each other count as the same recurring charge.
AMOUNT_TOLERANCE = Decimal("0.05")


def next_monthly_date(day_of_month: int, after: date) -> date:
    """First date strictly after ``after`` falling on ``day_of_month``.

    Short months clamp to their last day (a charge on the 31st lands on the
    30th in November).
    """
    year, month = after.year, after.month
    for _ in range(3):
        last_day = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(day_of_month, last_day))
        if candidate > after:
            return candidate
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    raise AssertionError("unreachable: a later month always exists")


def _amounts_consistent(transactions: list[Transaction]) -> bool:
    amounts = [abs(t.amount) for t in transactions]
    smallest, largest = min(amounts), max(amounts)
    return largest - smallest <= largest * AMOUNT_TOLERANCE


def detect_recurring(
    transactions: list[Transaction], as_of: date
) -> list[RecurringObligation]:
    """Group by merchant and account; keep groups that are flagged recurring or
    repeat in two or more months with a stable amount."""
    groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for t in transactions:
        if not is_internal_transfer(t):
            groups[(t.merchant_name, t.account_id)].append(t)

    obligations: list[RecurringObligation] = []
    for (merchant, account_id), items in groups.items():
        months = {(t.booking_date.year, t.booking_date.month) for t in items}
        flagged = any(t.is_recurring for t in items)
        repeats = len(months) >= 2 and _amounts_consistent(items)
        if not (flagged or repeats):
            continue

        latest = max(items, key=lambda t: t.booking_date)
        day = latest.booking_date.day
        obligations.append(
            RecurringObligation(
                merchant_name=merchant,
                account_id=account_id,
                category=categorize(latest),
                amount=latest.amount,
                day_of_month=day,
                next_due_date=next_monthly_date(day, as_of),
            )
        )

    return sorted(obligations, key=lambda o: (o.next_due_date, o.merchant_name))
