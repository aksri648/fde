from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.handoffs import router as handoffs_router
from app.api.health import router as health_router
from app.api.planning import router as planning_router
from app.api.sessions import router as sessions_router
from app.api.websocket import router as ws_router
from app.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("fde_backend.startup", env=settings.app_env.value)

    # Ensure the schema exists without ever destroying data. metadata.create_all
    # runs with checkfirst=True, so it only creates tables that are missing and
    # never drops or truncates existing tables. This makes startup safe to run
    # repeatedly against a persistent database (e.g. Neon) with no data loss.
    import app.db.models  # noqa: F401 - register ORM models on Base.metadata
    from app.db.base import Base
    from app.db.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("fde_backend.schema_ready")

    yield
    logger.info("fde_backend.shutdown")


app = FastAPI(
    title="FDE Backend",
    description="Forward Deployed Engineer planning and routing backend",
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

app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(planning_router)
app.include_router(handoffs_router)
app.include_router(ws_router)
