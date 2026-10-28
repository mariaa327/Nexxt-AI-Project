"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, DatabaseNotConfiguredError, get_engine

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables on startup when explicitly enabled and configured.

    ``create_all`` is a hackathon convenience only. Production schema changes
    should go through migrations (for example Alembic) instead.
    """
    if settings.auto_create_tables:
        if not settings.database_url:
            logger.info(
                "AUTO_CREATE_TABLES is on but DATABASE_URL is unset; skipping table creation."
            )
        else:
            # Import models so their tables are registered on Base.metadata
            # before create_all runs.
            from app import models  # noqa: F401

            try:
                Base.metadata.create_all(bind=get_engine())
                logger.info("Database tables are ready.")
            except DatabaseNotConfiguredError:
                logger.warning("Database is not configured; skipping table creation.")
            except Exception as exc:  # noqa: BLE001 - startup must not crash
                logger.warning(
                    "Automatic table creation failed (%s).", type(exc).__name__
                )
    yield


app = FastAPI(
    title="AI Hackathon API",
    description="Starter backend: Supabase-authenticated AI agent runs persisted to PostgreSQL.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
