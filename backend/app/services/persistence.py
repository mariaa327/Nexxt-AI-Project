"""Best-effort persistence of analyses.

The recommendation is the product; the stored row is a record. A missing or
failing database is logged and reported as ``persisted: false``, never raised.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.domain import AgentTask
from app.schemas.insights import AgentRecommendation, BillDecision

logger = logging.getLogger(__name__)


def save_analysis(
    db: Session | None,
    customer_id: str,
    decision: BillDecision,
    recommendation: AgentRecommendation,
) -> UUID | None:
    if db is None:
        return None
    task = AgentTask(
        customer_id=customer_id,
        decision=decision.model_dump(mode="json"),
        recommendation=recommendation.model_dump(mode="json"),
    )
    try:
        db.add(task)
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Analysis not persisted: %s", type(exc).__name__)
        return None
    return task.id
