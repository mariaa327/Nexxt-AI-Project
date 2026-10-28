"""Day-by-day projection of the current-account balance."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from app.schemas.insights import Projection, ProjectionPoint, UpcomingPayment

# Horizon when no income is scheduled: roughly one billing cycle.
DEFAULT_HORIZON_DAYS = 35


def project_balance(
    opening_balance: Decimal, as_of: date, payments: list[UpcomingPayment]
) -> Projection:
    """Project end-of-day balances from ``as_of`` through the next income.

    ``opening_balance`` already includes everything booked up to and including
    ``as_of``, so only payments due after it are applied. Balances are end of
    day: a bill and a salary on the same day net out, which matches a bank
    settling credits before debits.
    """
    future = [p for p in payments if p.due_date > as_of]
    next_income = min((p.due_date for p in future if p.amount > 0), default=None)
    horizon_end = next_income or as_of + timedelta(days=DEFAULT_HORIZON_DAYS)

    by_day: dict[date, list[UpcomingPayment]] = defaultdict(list)
    for p in future:
        by_day[p.due_date].append(p)

    points: list[ProjectionPoint] = []
    balance = opening_balance
    day = as_of
    while day <= horizon_end:
        events: list[str] = []
        for p in sorted(by_day.get(day, []), key=lambda p: p.amount < 0):
            balance += p.amount
            events.append(f"{p.merchant_name} {p.amount:+.2f}")
        points.append(ProjectionPoint(date=day, balance=balance, events=events))
        day += timedelta(days=1)

    negative = [p for p in points if p.balance < 0]
    lowest = min(points, key=lambda p: p.balance)
    return Projection(
        points=points,
        horizon_end=horizon_end,
        next_income_date=next_income,
        lowest_balance=lowest.balance,
        lowest_balance_date=lowest.date,
        first_deficit_date=negative[0].date if negative else None,
        peak_deficit=-lowest.balance if negative else Decimal(0),
        peak_deficit_date=lowest.date if negative else None,
        deficit_days=len(negative),
        deficit_exposure=sum((-p.balance for p in negative), Decimal(0)),
    )
