"""Dashboard endpoint: the deterministic picture for the logged-in user, no AI call."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ClientSession
from app.schemas.insights import BillDecision
from app.services import client_repository
from app.services.banking.engine import build_decision

router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=BillDecision,
    summary="Balances, upcoming payments, projection and priced options",
    responses={401: {"description": "Not logged in"}},
)
def get_dashboard(session: ClientSession) -> BillDecision:
    return build_decision(client_repository.load_snapshot(session))
