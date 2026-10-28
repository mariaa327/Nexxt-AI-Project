"""Payment verification and execution of the chosen option.

There is no real banking integration: executing an option changes the client's
balances in their own database. Execution requires a verification challenge,
simulating 3-D Secure style approval in the banking app: ``initiate`` creates a
pending challenge, it is approved automatically after ``demo_approval_seconds``,
and only an approved, unused, unexpired challenge can be executed, once.

Challenges live in memory and belong to one user; another user's challenge id
is treated as unknown.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from threading import Lock

from app.core.config import settings
from app.schemas.banking import ClientSnapshot, ScheduledPayment
from app.schemas.insights import (
    BillDecision,
    Challenge,
    ChallengeStatus,
    CostOption,
    ExecuteResponse,
)
from app.services.banking.engine import (
    ACCOUNT_LABELS,
    account_balances,
    build_decision,
)
from app.services.banking.options import day_label, ron
from app.services.errors import (
    ChallengeExpiredError,
    ChallengeNotApprovedError,
    ChallengeNotFoundError,
    OptionNotAvailableError,
)

CHALLENGE_TTL_SECONDS = 120.0


@dataclass
class _PendingChallenge:
    owner: str
    challenge: Challenge
    created_at: float
    approve_after: float
    # "pending" until cancelled or used; approval and expiry derive from time.
    state: ChallengeStatus = "pending"


class ChallengeStore:
    """Process-wide store of verification challenges, keyed by owner."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = Lock()
        self._challenges: dict[str, _PendingChallenge] = {}

    def _status(self, pending: _PendingChallenge) -> ChallengeStatus:
        if pending.state != "pending":
            return pending.state
        elapsed = self._clock() - pending.created_at
        if elapsed > CHALLENGE_TTL_SECONDS:
            return "expired"
        return "approved" if elapsed >= pending.approve_after else "pending"

    def _view(self, pending: _PendingChallenge) -> Challenge:
        return pending.challenge.model_copy(update={"status": self._status(pending)})

    def _get(self, owner: str, challenge_id: str) -> _PendingChallenge:
        pending = self._challenges.get(challenge_id)
        if pending is None or pending.owner != owner:
            raise ChallengeNotFoundError()
        return pending

    def initiate(
        self, owner: str, snapshot: ClientSnapshot, option_id: str
    ) -> Challenge:
        """Start verification for an option that is currently offered."""
        decision = build_decision(snapshot)
        option = _offered(decision, option_id)
        if option.option_id == "overdraft":
            # Nothing is paid or moved, so there is nothing to authorise.
            raise OptionNotAvailableError()

        source = next(
            (a for a in snapshot.accounts if a.account_id == option.source_account_id),
            None,
        )
        if option.option_id == "credit_card" and decision.triggering_payment:
            merchant = decision.triggering_payment.merchant_name
        else:
            merchant = "Transfer to your current account"
        approve_after = settings.demo_approval_seconds

        challenge = Challenge(
            challenge_id=uuid.uuid4().hex,
            option_id=option.option_id,
            merchant_name=merchant,
            amount=option.amount,
            source_label=ACCOUNT_LABELS[source.account_type]
            if source
            else option.label,
            masked_account=f"•••• {source.iban[-4:]}"
            if source and source.iban
            else None,
            status="pending",
            approve_after_seconds=approve_after,
            expires_in_seconds=CHALLENGE_TTL_SECONDS,
        )
        with self._lock:
            self._challenges[challenge.challenge_id] = _PendingChallenge(
                owner=owner,
                challenge=challenge,
                created_at=self._clock(),
                approve_after=approve_after,
            )
        return challenge

    def challenge(self, owner: str, challenge_id: str) -> Challenge:
        with self._lock:
            return self._view(self._get(owner, challenge_id))

    def cancel(self, owner: str, challenge_id: str) -> Challenge:
        with self._lock:
            pending = self._get(owner, challenge_id)
            if self._status(pending) in ("pending", "approved"):
                pending.state = "cancelled"
            return self._view(pending)

    def consume(self, owner: str, challenge_id: str) -> Challenge:
        """Mark an approved challenge used and return it; each works once."""
        with self._lock:
            pending = self._get(owner, challenge_id)
            status = self._status(pending)
            if status == "expired":
                raise ChallengeExpiredError()
            if status != "approved":
                raise ChallengeNotApprovedError()
            pending.state = "used"
            return pending.challenge

    def clear(self, owner: str) -> None:
        with self._lock:
            self._challenges = {
                k: v for k, v in self._challenges.items() if v.owner != owner
            }


def apply_option(
    before: ClientSnapshot, option_id: str
) -> tuple[ClientSnapshot, ExecuteResponse]:
    """The client's data after carrying out ``option_id``. Pure: ``before`` is untouched."""
    decision = build_decision(before)
    option = _offered(decision, option_id)

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
                ScheduledPayment(**p.model_dump()) for p in decision.upcoming_payments
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
        message = f"{ron(option.amount)} moved from savings to your current account."
    else:
        message = "No action taken; the current account will use the overdraft."

    return after, ExecuteResponse(
        option_id=option.option_id,
        message=message,
        balances_before=account_balances(before),
        balances_after=account_balances(after),
        decision_after=build_decision(after),
    )


def _offered(decision: BillDecision, option_id: str) -> CostOption:
    option = next((o for o in decision.options if o.option_id == option_id), None)
    if option is None or not option.feasible:
        raise OptionNotAvailableError()
    return option


challenge_store = ChallengeStore()
