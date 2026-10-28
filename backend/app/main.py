"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.router import api_router
from app.core.config import settings
from app.core.database import router
from app.services.errors import AgentServiceError, DatabaseUnavailableError
from app.services.provisioning import provision

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create and seed the demo databases when enabled.

    ``provision`` is idempotent and a development convenience; production
    schema changes would go through migrations. Startup never fails because
    PostgreSQL is down: requests then get a clear 503.
    """
    if settings.provision_on_startup:
        try:
            provision(router)
        except SQLAlchemyError as exc:
            logger.warning(
                "Database provisioning skipped (%s). Is PostgreSQL running?",
                type(exc).__name__,
            )
    yield
    router.dispose()


app = FastAPI(
    title="Overdraft Agent API",
    description=(
        "Deterministic overdraft forecasting and option pricing, phrased by an LLM. "
        "Fictional clients, each with their own PostgreSQL database."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


@app.exception_handler(AgentServiceError)
def handle_service_error(_: Request, exc: AgentServiceError) -> JSONResponse:
    """Service errors carry safe, human-readable messages."""
    return JSONResponse(
        status_code=exc.http_status, content={"detail": exc.public_message}
    )


@app.exception_handler(OperationalError)
def handle_database_down(_: Request, exc: OperationalError) -> JSONResponse:
    """PostgreSQL unreachable: a readable 503, never a stack trace."""
    logger.error("Database operation failed: %s", type(exc.orig).__name__)
    error = DatabaseUnavailableError()
    return JSONResponse(
        status_code=error.http_status, content={"detail": error.public_message}
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
