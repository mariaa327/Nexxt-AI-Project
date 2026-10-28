"""In-memory demo state and execution of the chosen option.

There is no real banking integration: executing an option changes the demo
client's balances in memory so the dashboard can show the result. ``reset``
reloads the data file.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from threading import Lock

from app.schemas.banking import ClientSnapshot, ScheduledPayment
from app.schemas.insights import ExecuteResponse
from app.services.banking.engine import account_balances, build_decision
from app.services.banking.loader import load_snapshot
from app.services.banking.options import day_label, ron
from app.services.errors import OptionNotAvailableError


class DemoState:
    def __init__(self, loader: Callable[[], ClientSnapshot] = load_snapshot) -> None:
        self._loader = loader
        self._lock = Lock()
        self._snapshot: ClientSnapshot | None = None

    def _current(self) -> ClientSnapshot:
        if self._snapshot is None:
            self._snapshot = self._loader()
        return self._snapshot

    def snapshot(self) -> ClientSnapshot:
        """A copy of the current state; callers cannot mutate it by accident."""
        with self._lock:
            return self._current().model_copy(deep=True)

    def reset(self) -> None:
        with self._lock:
            self._snapshot = self._loader()

    def execute(self, option_id: str) -> ExecuteResponse:
        with self._lock:
            before = self._current()
            decision = build_decision(before)
            option = next(
                (o for o in decision.options if o.option_id == option_id), None
            )
            if option is None or not option.feasible:
                raise OptionNotAvailableError()

            after = before.model_copy(deep=True)
            current = after.current_account()
            assert current is not None

            if option.option_id == "credit_card":
                card = after.credit_card()
                trigger = decision.triggering_payment
                assert card is not None and trigger is not None
                if not after.scheduled_payments:
                    # Inferred payments become explicit so the change sticks.
                    after.scheduled_payments = [
                        ScheduledPayment(**p.model_dump())
                        for p in decision.upcoming_payments
                    ]
                for payment in after.scheduled_payments:
                    if payment.payment_id == trigger.payment_id:
                        payment.account_id = card.account_id
                card.available_balance -= option.amount
                message = (
                    f"{trigger.merchant_name} ({ron(option.amount)}) will be paid from your "
                    f"credit card on {day_label(trigger.due_date)}."
                )
            elif option.option_id == "savings":
                savings = after.savings_account()
                assert savings is not None
                savings.available_balance -= option.amount
                current.available_balance += option.amount
                if after.product_parameters.savings.early_withdrawal_forfeits_interest:
                    savings.accrued_interest = Decimal(0)
                message = (
                    f"{ron(option.amount)} moved from savings to your current account."
                )
            else:
                message = "No action taken; the current account will use the overdraft."

            self._snapshot = after
            return ExecuteResponse(
                option_id=option.option_id,
                message=message,
                balances_before=account_balances(before),
                balances_after=account_balances(after),
                decision_after=build_decision(after),
            )


demo_state = DemoState()
