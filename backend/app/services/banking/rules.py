"""Deterministic recommendation text, used when the model is unavailable or
its output does not match the engine's decision."""

from __future__ import annotations

from app.schemas.insights import AgentRecommendation, BillDecision
from app.services.banking.options import day_label, ron

# Option as the subject of a sentence: "<subject> costs 0.00 RON."
SUBJECTS = {
    "credit_card": "Paying with the credit card",
    "savings": "Withdrawing from savings",
    "overdraft": "Using the overdraft",
}


def rules_recommendation(
    decision: BillDecision, fallback_reason: str | None = None
) -> AgentRecommendation:
    projection = decision.projection

    if decision.no_action_needed or not decision.options:
        horizon = day_label(projection.horizon_end)
        reasons = [
            f"Every scheduled payment on your current account is covered until {horizon}.",
            (
                f"Your lowest projected balance is {ron(projection.lowest_balance)} "
                f"on {day_label(projection.lowest_balance_date)}."
            ),
        ]
        if projection.next_income_date is not None:
            reasons.append(
                f"Your next income is expected on {day_label(projection.next_income_date)}."
            )
        return AgentRecommendation(
            status="no_risk",
            recommended_option_id=None,
            headline=f"No action needed: your current account covers every bill until {horizon}.",
            reasons=reasons,
            trade_offs=[],
            generated_by="rules",
            fallback_reason=fallback_reason,
        )

    best = decision.options[0]
    trigger = decision.triggering_payment
    reasons: list[str] = []
    if trigger is not None and projection.first_deficit_date is not None:
        reasons.append(
            f"Your current account would go negative on {day_label(projection.first_deficit_date)} "
            f"when {trigger.merchant_name} collects {ron(-trigger.amount)}, and stay negative "
            f"for {projection.deficit_days} days, down to -{ron(projection.peak_deficit)}."
        )
    overdraft = next((o for o in decision.options if o.option_id == "overdraft"), None)
    if overdraft is not None and best.option_id != "overdraft":
        reasons.append(
            f"Doing nothing would cost {ron(overdraft.cost)}. {overdraft.explanation}"
        )
    reasons.append(
        f"{SUBJECTS[best.option_id]} costs {ron(best.cost)}. {best.explanation}"
    )
    if decision.saving_vs_doing_nothing > 0:
        reasons.append(
            f"That saves you {ron(decision.saving_vs_doing_nothing)} compared with doing nothing."
        )
    savings = next(
        (b for b in decision.balances if b.account_type == "SAVINGS_ACCOUNT"), None
    )
    if savings is not None and best.option_id != "savings" and savings.accrued_interest:
        reasons.append(
            f"Your savings stay untouched, so you keep the {ron(savings.accrued_interest)} "
            "of interest already accrued."
        )
    if not best.prevents_overdraft and best.option_id != "overdraft":
        reasons.append(
            "This does not fully cover the gap; the current account may still dip below zero."
        )

    return AgentRecommendation(
        status="action_required",
        recommended_option_id=best.option_id,
        headline=best.action,
        reasons=reasons,
        trade_offs=[
            f"{o.label}: {ron(o.cost)}. {o.explanation}"
            + ("" if o.feasible else " Not enough funds to do this in full.")
            for o in decision.options[1:]
        ],
        generated_by="rules",
        fallback_reason=fallback_reason,
    )
