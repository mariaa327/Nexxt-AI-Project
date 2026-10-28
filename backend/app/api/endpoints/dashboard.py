"""Dashboard endpoint: the deterministic picture, no AI call."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_demo_state
from app.schemas.insights import BillDecision
from app.services.banking.engine import build_decision
from app.services.banking.executor import DemoState

router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=BillDecision,
    summary="Balances, upcoming payments, projection and priced options",
)
def get_dashboard(state: Annotated[DemoState, Depends(get_demo_state)]) -> BillDecision:
    return build_decision(state.snapshot())
