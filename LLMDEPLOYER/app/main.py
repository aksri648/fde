from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import sessions, questions, websocket, health
from app.config import get_settings
from app.utils.logger import get_logger
from app.security import configure_api_key

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    llmdeployer_api_key = getattr(settings, "LLMDEPLOYER_API_KEY", "")
    if llmdeployer_api_key:
        configure_api_key(llmdeployer_api_key)
    else:
        logger.warning(
            "LLMDEPLOYER_API_KEY is not set. Authentication is DISABLED (dev-mode)."
        )
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY is not set. Claude Agent SDK will not work.")
    providers = {
        "azure": bool(settings.AZURE_SUBSCRIPTION_ID),
        "runpod": bool(settings.RUNPOD_API_KEY),
        "modal": bool(settings.MODAL_TOKEN_ID),
        "nim": bool(settings.NGC_API_KEY),
    }
    logger.info(f"LLMDeployer started. Configured providers: {providers}")

    yield

    from app.services.connection_manager import connection_manager
    for session_id in list(connection_manager.active_connections.keys()):
        for ws in connection_manager.active_connections[session_id]:
            try:
                await ws.close()
            except Exception:
                pass
    connection_manager.active_connections.clear()
    logger.info("LLMDeployer shut down.")


app = FastAPI(
    title="LLMDeployer API",
    description="Headless microservice for intelligent LLM deployment orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(websocket.router, prefix="/api")
