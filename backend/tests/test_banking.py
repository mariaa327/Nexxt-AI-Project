"""Engine tests against the bundled demo data, with hand-checked values."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.banking import ClientSnapshot, SavingsAccount, ScheduledPayment
from app.schemas.insights import ExecuteResponse
from app.services.banking.categorizer import MCC_CATEGORIES, categorize
from app.services.banking.engine import build_decision
from app.services.banking.executor import ChallengeStore, apply_option
from app.services.banking.loader import load_snapshot
from app.services.banking.recurring import detect_recurring, next_monthly_date
from app.services.banking.rules import rules_recommendation
from app.services.errors import (
    BankingDataError,
    ChallengeExpiredError,
    ChallengeNotApprovedError,
    ChallengeNotFoundError,
    OptionNotAvailableError,
)
from tests.conftest import FakeClock


def _costs(snapshot: ClientSnapshot) -> dict[str, Decimal]:
    return {o.option_id: o.cost for o in build_decision(snapshot).options}


# --- Projection -------------------------------------------------------------


def test_projection_first_deficit(snapshot: ClientSnapshot) -> None:
    assert build_decision(snapshot).projection.first_deficit_date == date(2026, 11, 5)


def test_projection_peak_deficit(snapshot: ClientSnapshot) -> None:
    projection = build_decision(snapshot).projection
    assert projection.peak_deficit == Decimal("318.40")
    assert projection.peak_deficit_date == date(2026, 11, 9)


def test_projection_days_negative(snapshot: ClientSnapshot) -> None:
    projection = build_decision(snapshot).projection
    negative = [p.date for p in projection.points if p.balance < 0]
    assert negative == [date(2026, 11, d) for d in range(5, 10)]
    assert projection.deficit_days == 5
    assert projection.deficit_exposure == Decimal("992.00")


def test_projection_ends_at_next_income(snapshot: ClientSnapshot) -> None:
    projection = build_decision(snapshot).projection
    assert projection.horizon_end == date(2026, 11, 10)
    assert projection.points[-1].balance == Decimal("6981.60")


def test_bill_on_payday_is_covered(snapshot: ClientSnapshot) -> None:
    current = snapshot.current_account()
    assert current is not None
    current.available_balance = Decimal("100.00")
    snapshot.scheduled_payments = [
        ScheduledPayment(
            payment_id="BILL",
            account_id=current.account_id,
            due_date=date(2026, 11, 10),
            amount=Decimal("-500.00"),
            merchant_name="Bill",
        ),
        ScheduledPayment(
            payment_id="SALARY",
            account_id=current.account_id,
            due_date=date(2026, 11, 10),
            amount=Decimal("1000.00"),
            merchant_name="Salary",
        ),
    ]
    decision = build_decision(snapshot)
    assert decision.no_action_needed
    assert decision.projection.points[-1].balance == Decimal("600.00")


# --- Option pricing ---------------------------------------------------------


def test_overdraft_cost_uses_daily_balances(snapshot: ClientSnapshot) -> None:
    cost = _costs(snapshot)["overdraft"]
    assert cost == Decimal("31.19")  # 30.00 + 992.00 x 0.0012
    # Pricing the peak for every day would overstate it.
    assert cost != Decimal("31.91")


def test_savings_cost_is_forfeited_interest(snapshot: ClientSnapshot) -> None:
    assert _costs(snapshot)["savings"] == Decimal("12.40")


def test_credit_card_cost_zero_in_grace(snapshot: ClientSnapshot) -> None:
    assert _costs(snapshot)["credit_card"] == Decimal("0.00")


def test_credit_card_charges_interest_beyond_grace(snapshot: ClientSnapshot) -> None:
    snapshot.product_parameters.credit_card.grace_period_days = 3
    # 618.40 x 0.24 / 365 x 5 days
    assert _costs(snapshot)["credit_card"] == Decimal("2.03")


def test_options_ranked_cheapest_first(snapshot: ClientSnapshot) -> None:
    decision = build_decision(snapshot)
    assert [o.option_id for o in decision.options] == [
        "credit_card",
        "savings",
        "overdraft",
    ]
    assert decision.recommended_option_id == "credit_card"
    assert decision.saving_vs_doing_nothing == Decimal("31.19")
    assert decision.triggering_payment is not None
    assert decision.triggering_payment.merchant_name == "Enel Energie"


def test_savings_more_expensive_than_overdraft(snapshot: ClientSnapshot) -> None:
    savings = snapshot.savings_account()
    assert savings is not None
    savings.accrued_interest = Decimal("60.00")
    decision = build_decision(snapshot)
    assert [o.option_id for o in decision.options] == [
        "credit_card",
        "overdraft",
        "savings",
    ]


def test_missing_savings_account_omits_option(snapshot: ClientSnapshot) -> None:
    snapshot.accounts = [
        a for a in snapshot.accounts if not isinstance(a, SavingsAccount)
    ]
    decision = build_decision(snapshot)
    assert [o.option_id for o in decision.options] == ["credit_card", "overdraft"]


def test_insufficient_funds_falls_back_to_overdraft(snapshot: ClientSnapshot) -> None:
    savings, card = snapshot.savings_account(), snapshot.credit_card()
    assert savings is not None and card is not None
    savings.available_balance = Decimal("100.00")
    card.available_balance = Decimal("100.00")
    decision = build_decision(snapshot)
    assert decision.recommended_option_id == "overdraft"
    assert [o.feasible for o in decision.options] == [True, False, False]


def test_no_deficit_returns_no_risk(snapshot: ClientSnapshot) -> None:
    current = snapshot.current_account()
    assert current is not None
    current.available_balance = Decimal("2845.50")
    decision = build_decision(snapshot)
    assert decision.no_action_needed
    assert decision.options == []
    assert decision.recommended_option_id is None
    recommendation = rules_recommendation(decision)
    assert recommendation.status == "no_risk"
    assert recommendation.trade_offs == []


# --- History ----------------------------------------------------------------


def test_internal_transfers_excluded(snapshot: ClientSnapshot) -> None:
    situation = build_decision(snapshot).situation
    assert situation.total_income == Decimal("9700.00")
    assert situation.total_spend == Decimal("6021.28")


def test_categories_match_fixture_labels(snapshot: ClientSnapshot) -> None:
    with_mcc = [t for t in snapshot.transactions if t.mcc]
    assert with_mcc
    for t in with_mcc:
        assert t.mcc in MCC_CATEGORIES
        assert categorize(t) == t.category, t.transaction_id


def test_recurring_detection_finds_seven(snapshot: ClientSnapshot) -> None:
    found = {
        o.merchant_name: (o.day_of_month, o.account_id)
        for o in detect_recurring(snapshot.transactions, date(2026, 10, 28))
    }
    assert found == {
        "Spotify": (1, "ACC-CREDIT-002"),
        "World Class": (9, "ACC-DEBIT-001"),
        "Tech Solutions SRL": (10, "ACC-DEBIT-001"),
        "Popa Ionut": (10, "ACC-DEBIT-001"),
        "Enel Energie": (12, "ACC-DEBIT-001"),
        "Netflix.com": (25, "ACC-DEBIT-001"),
        "Orange Romania": (26, "ACC-DEBIT-001"),
    }


def test_next_monthly_date_clamps_short_months() -> None:
    assert next_monthly_date(31, date(2026, 10, 31)) == date(2026, 11, 30)
    assert next_monthly_date(5, date(2026, 12, 20)) == date(2027, 1, 5)


def test_falls_back_to_recurring_history(snapshot: ClientSnapshot) -> None:
    snapshot.scheduled_payments = []
    decision = build_decision(snapshot)
    assert decision.payments_source == "recurring_history"
    merchants = [p.merchant_name for p in decision.upcoming_payments]
    assert "Spotify" not in merchants  # billed to the credit card
    assert {"World Class", "Popa Ionut", "Tech Solutions SRL"} <= set(merchants)


# --- Loading ----------------------------------------------------------------


def test_malformed_fixture_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"customer": {}}', encoding="utf-8")
    with pytest.raises(BankingDataError):
        load_snapshot(bad)


def test_missing_fixture_raises(tmp_path: Path) -> None:
    with pytest.raises(BankingDataError):
        load_snapshot(tmp_path / "absent.json")


# --- Verification and execution --------------------------------------------

OWNER = "andrei"


def _approve_and_apply(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock, option_id: str
) -> ExecuteResponse:
    challenge_id = store.initiate(OWNER, snapshot, option_id).challenge_id
    clock.advance(3)
    challenge = store.consume(OWNER, challenge_id)
    return apply_option(snapshot, challenge.option_id)[1]


def test_execute_credit_card_clears_deficit(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock
) -> None:
    result = _approve_and_apply(snapshot, store, clock, "credit_card")
    assert result.decision_after.no_action_needed
    card = next(b for b in result.balances_after if b.account_type == "CREDIT_CARD")
    assert card.balance == Decimal("7531.60")


def test_execute_savings_clears_deficit(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock
) -> None:
    result = _approve_and_apply(snapshot, store, clock, "savings")
    assert result.decision_after.no_action_needed
    after = {b.account_type: b for b in result.balances_after}
    assert after["CURRENT_ACCOUNT"].balance == Decimal("768.40")
    assert after["SAVINGS_ACCOUNT"].balance == Decimal("11681.60")
    assert after["SAVINGS_ACCOUNT"].accrued_interest == Decimal(0)


def test_apply_option_leaves_input_untouched(snapshot: ClientSnapshot) -> None:
    before = snapshot.model_dump()
    apply_option(snapshot, "credit_card")
    assert snapshot.model_dump() == before


def test_challenge_describes_the_payment(
    snapshot: ClientSnapshot, store: ChallengeStore
) -> None:
    challenge = store.initiate(OWNER, snapshot, "credit_card")
    assert challenge.status == "pending"
    assert challenge.merchant_name == "Enel Energie"
    assert challenge.amount == Decimal("618.40")
    assert challenge.source_label == "Credit card"
    assert challenge.masked_account == "•••• 0000"


def test_challenge_approves_after_delay(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock
) -> None:
    challenge_id = store.initiate(OWNER, snapshot, "credit_card").challenge_id
    clock.advance(2.9)
    assert store.challenge(OWNER, challenge_id).status == "pending"
    clock.advance(0.1)
    assert store.challenge(OWNER, challenge_id).status == "approved"


def test_consume_before_approval_is_refused(
    snapshot: ClientSnapshot, store: ChallengeStore
) -> None:
    challenge_id = store.initiate(OWNER, snapshot, "credit_card").challenge_id
    with pytest.raises(ChallengeNotApprovedError):
        store.consume(OWNER, challenge_id)


def test_challenge_works_once(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock
) -> None:
    challenge_id = store.initiate(OWNER, snapshot, "credit_card").challenge_id
    clock.advance(3)
    store.consume(OWNER, challenge_id)
    assert store.challenge(OWNER, challenge_id).status == "used"
    with pytest.raises(ChallengeNotApprovedError):
        store.consume(OWNER, challenge_id)


def test_cancelled_challenge_cannot_execute(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock
) -> None:
    challenge_id = store.initiate(OWNER, snapshot, "credit_card").challenge_id
    assert store.cancel(OWNER, challenge_id).status == "cancelled"
    clock.advance(3)
    with pytest.raises(ChallengeNotApprovedError):
        store.consume(OWNER, challenge_id)


def test_expired_challenge_cannot_execute(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock
) -> None:
    challenge_id = store.initiate(OWNER, snapshot, "credit_card").challenge_id
    clock.advance(121)
    assert store.challenge(OWNER, challenge_id).status == "expired"
    with pytest.raises(ChallengeExpiredError):
        store.consume(OWNER, challenge_id)


def test_challenge_belongs_to_its_owner(
    snapshot: ClientSnapshot, store: ChallengeStore, clock: FakeClock
) -> None:
    challenge_id = store.initiate(OWNER, snapshot, "credit_card").challenge_id
    clock.advance(3)
    with pytest.raises(ChallengeNotFoundError):
        store.challenge("maria", challenge_id)
    with pytest.raises(ChallengeNotFoundError):
        store.consume("maria", challenge_id)


def test_unknown_challenge_raises(store: ChallengeStore) -> None:
    with pytest.raises(ChallengeNotFoundError):
        store.consume(OWNER, "missing")


def test_initiate_unavailable_option_raises(
    snapshot: ClientSnapshot, store: ChallengeStore
) -> None:
    with pytest.raises(OptionNotAvailableError):
        store.initiate(OWNER, snapshot, "overdraft")
    paid, _ = apply_option(snapshot, "credit_card")
    with pytest.raises(OptionNotAvailableError):
        store.initiate(OWNER, paid, "savings")


def test_clear_drops_only_that_users_challenges(
    snapshot: ClientSnapshot, store: ChallengeStore
) -> None:
    mine = store.initiate(OWNER, snapshot, "credit_card").challenge_id
    theirs = store.initiate("maria", snapshot, "credit_card").challenge_id
    store.clear(OWNER)
    with pytest.raises(ChallengeNotFoundError):
        store.challenge(OWNER, mine)
    assert store.challenge("maria", theirs).status == "pending"
