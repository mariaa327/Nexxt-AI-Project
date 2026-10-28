"""Transaction categorisation and the month's descriptive totals."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from app.schemas.banking import Transaction
from app.schemas.insights import CategoryTotal, RecurringObligation, SituationSummary

# Merchant category codes (ISO 18245) seen in Romanian card data.
MCC_CATEGORIES: dict[str, str] = {
    "4121": "Transportation",
    "4511": "Travel",
    "4814": "Utilities",
    "4900": "Utilities",
    "5411": "Groceries",
    "5541": "Transportation",
    "5651": "Shopping",
    "5712": "Shopping",
    "5732": "Electronics",
    "5812": "Food & Dining",
    "5813": "Entertainment",
    "5814": "Food & Dining",
    "5815": "Entertainment",
    "5912": "Health",
    "6011": "Cash",
    "7832": "Entertainment",
    "7997": "Lifestyle",
}


def categorize(transaction: Transaction) -> str:
    """Category from the MCC; the bank's own label when there is no MCC."""
    if transaction.mcc and transaction.mcc in MCC_CATEGORIES:
        return MCC_CATEGORIES[transaction.mcc]
    return transaction.category or "Uncategorized"


def is_internal_transfer(transaction: Transaction) -> bool:
    """Money moved between the client's own accounts: neither income nor spend."""
    return transaction.payment_method == "INTERNAL_TRANSFER"


def summarize(
    transactions: Iterable[Transaction], recurring: list[RecurringObligation]
) -> SituationSummary:
    external = [t for t in transactions if not is_internal_transfer(t)]
    income = Decimal(0)
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    for t in external:
        if t.amount > 0:
            income += t.amount
        else:
            by_category[categorize(t)] += -t.amount

    dates = [t.booking_date.date() for t in external]
    return SituationSummary(
        period_start=min(dates, default=None),
        period_end=max(dates, default=None),
        total_income=income,
        total_spend=sum(by_category.values(), Decimal(0)),
        spend_by_category=[
            CategoryTotal(category=name, amount=amount)
            for name, amount in sorted(by_category.items(), key=lambda kv: -kv[1])
        ],
        recurring=recurring,
    )
