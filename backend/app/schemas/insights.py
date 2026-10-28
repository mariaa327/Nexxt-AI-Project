"""Engine output (the decision) and the recommendation built from it.

``BillDecision`` is computed deterministically and is the only input the LLM
ever sees. ``RecommendationDraft`` is the structured output requested from the
model; ``AgentRecommendation`` adds where the wording came from.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.banking import Money

OptionId = Literal["credit_card", "savings", "overdraft"]


class AccountBalance(BaseModel):
    account_id: str
    account_type: str
    label: str
    balance: Money
    credit_limit: Money | None = None
    accrued_interest: Money | None = None


class CategoryTotal(BaseModel):
    category: str
    amount: Money


class RecurringObligation(BaseModel):
    merchant_name: str
    account_id: str
    category: str | None
    amount: Money
    day_of_month: int
    next_due_date: date


class SituationSummary(BaseModel):
    """What the client's month looked like. Descriptive only, no advice."""

    period_start: date | None
    period_end: date | None
    total_income: Money
    total_spend: Money
    spend_by_category: list[CategoryTotal]
    recurring: list[RecurringObligation]


class UpcomingPayment(BaseModel):
    payment_id: str
    account_id: str
    due_date: date
    amount: Money
    merchant_name: str
    category: str | None = None
    description: str = ""


class ProjectionPoint(BaseModel):
    date: date
    balance: Money
    events: list[str] = Field(default_factory=list)


class Projection(BaseModel):
    """End-of-day current-account balance from today to the next income."""

    points: list[ProjectionPoint]
    horizon_end: date
    next_income_date: date | None
    lowest_balance: Money
    lowest_balance_date: date
    first_deficit_date: date | None
    peak_deficit: Money
    peak_deficit_date: date | None
    deficit_days: int
    # Sum of the daily negative balances; overdraft interest accrues on this.
    deficit_exposure: Money


class CostOption(BaseModel):
    option_id: OptionId
    label: str
    action: str
    amount: Money
    cost: Money
    formula: str
    explanation: str
    assumptions: list[str]
    # Can be carried out in full and leaves no negative day in the projection.
    prevents_overdraft: bool
    feasible: bool
    source_account_id: str | None = None


class BillDecision(BaseModel):
    customer_name: str
    as_of_date: date
    payments_source: Literal["scheduled", "recurring_history"]
    balances: list[AccountBalance]
    situation: SituationSummary
    upcoming_payments: list[UpcomingPayment]
    projection: Projection
    no_action_needed: bool
    triggering_payment: UpcomingPayment | None
    # Cheapest first.
    options: list[CostOption]
    recommended_option_id: OptionId | None
    # Cost of doing nothing minus cost of the recommended option.
    saving_vs_doing_nothing: Money = Decimal(0)


class RecommendationDraft(BaseModel):
    """Structured output requested from the model."""

    status: Literal["action_required", "no_risk"] = Field(
        ..., description="'no_risk' only when no_action_needed is true."
    )
    recommended_option_id: OptionId | None = Field(
        ..., description="Copy recommended_option_id from the input exactly."
    )
    headline: str = Field(..., description="One sentence stating the decision.")
    reasons: list[str] = Field(
        ...,
        description="Three to five bullet points, each one decision and why, using only "
        "numbers present in the input.",
    )
    trade_offs: list[str] = Field(
        ..., description="One bullet per option not recommended, with its cost."
    )


class AgentRecommendation(RecommendationDraft):
    generated_by: Literal["llm", "rules"]
    fallback_reason: str | None = None


class AnalyzeResponse(BaseModel):
    decision: BillDecision
    recommendation: AgentRecommendation
    task_id: UUID | None = None
    persisted: bool = False


class InitiateRequest(BaseModel):
    option_id: OptionId


ChallengeStatus = Literal["pending", "approved", "expired", "cancelled", "used"]


class Challenge(BaseModel):
    """A simulated payment verification awaiting approval in the banking app."""

    challenge_id: str
    option_id: OptionId
    merchant_name: str
    amount: Money
    source_label: str
    masked_account: str | None
    status: ChallengeStatus
    approve_after_seconds: float
    expires_in_seconds: float


class ExecuteRequest(BaseModel):
    challenge_id: str = Field(..., min_length=1, max_length=64)


class ExecuteResponse(BaseModel):
    option_id: OptionId
    message: str
    balances_before: list[AccountBalance]
    balances_after: list[AccountBalance]
    decision_after: BillDecision
