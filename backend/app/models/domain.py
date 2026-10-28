"""SQLAlchemy ORM models.

Models describe persistence only; API request/response shapes live in
``app.schemas``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

# JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AgentTask(Base):
    """One analysis: the engine's decision and the recommendation shown."""

    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    decision: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    recommendation: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Typical query: newest analyses for one customer.
        Index("ix_agent_tasks_customer_id_created_at", "customer_id", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<AgentTask id={self.id} customer_id={self.customer_id}>"
