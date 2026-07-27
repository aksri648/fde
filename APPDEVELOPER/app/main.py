import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, jobs, websocket
from app.db.models import Database
from app.repositories.job_repository import EventRepository, JobRepository
from app.security.auth import configure_api_key
from app.services.agent_service import AgentService
from app.services.architecture_service import ArchitectureService
from app.services.event_service import EventService
from app.services.github_service import GitHubService
from app.services.job_service import JobService
from app.services.review_service import ReviewService
from app.services.validation_service import ValidationService
from app.services.workspace_service import WorkspaceService

load_dotenv()

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./appdeveloper.db")
WORKSPACE_ROOT = os.getenv("APPDEVELOPER_WORKSPACE_ROOT", "./workspaces")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Point ANTHROPIC_BASE_URL at the LiteLLM proxy to route the Claude Agent SDK
# to your OpenAI-compatible backend. ANTHROPIC_MODEL is the model/alias to use.
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "")
APPDEVELOPER_API_KEY = os.getenv("APPDEVELOPER_API_KEY", "")
MAX_CONCURRENT_JOBS = int(os.getenv("APPDEVELOPER_MAX_CONCURRENT_JOBS", "5"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    db = Database(DATABASE_URL)
    await db.create_tables()

    job_repo = JobRepository(db)
    event_repo = EventRepository(db)

    workspace_service = WorkspaceService(WORKSPACE_ROOT)
    agent_service = AgentService(
        api_key=ANTHROPIC_API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        model=ANTHROPIC_MODEL,
    )
    event_service = EventService(event_repo, job_repo)
    validation_service = ValidationService(workspace_service)
    architecture_service = ArchitectureService(agent_service, event_service)
    review_service = ReviewService(
        agent_service, workspace_service, validation_service, event_service
    )
    github_service = GitHubService(workspace_service, event_service)

    job_service = JobService(
        job_repo=job_repo,
        workspace_service=workspace_service,
        architecture_service=architecture_service,
        agent_service=agent_service,
        validation_service=validation_service,
        review_service=review_service,
        github_service=github_service,
        event_service=event_service,
        max_concurrent=MAX_CONCURRENT_JOBS,
    )

    app.state.job_service = job_service
    app.state.event_service = event_service
    app.state.db = db

    if APPDEVELOPER_API_KEY:
        configure_api_key(APPDEVELOPER_API_KEY)

    logger.info("app_started", database_url=DATABASE_URL)

    yield

    await db.dispose()
    logger.info("app_stopped")


app = FastAPI(
    title="APPDEVELOPER",
    description="AI-powered app generation microservice",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(websocket.router)
