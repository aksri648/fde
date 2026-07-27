import httpx
from fastapi import APIRouter

from app.config import get_settings
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger("health")


@router.get("/health")
async def health_check():
    settings = get_settings()
    providers = {
        "azure": bool(settings.AZURE_TENANT_ID and settings.AZURE_CLIENT_ID and settings.AZURE_CLIENT_SECRET and settings.AZURE_SUBSCRIPTION_ID),
        "runpod": bool(settings.RUNPOD_API_KEY),
        "modal": bool(settings.MODAL_TOKEN_ID and settings.MODAL_TOKEN_SECRET),
        "nim": bool(settings.NGC_API_KEY),
    }

    litellm_proxy = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.LITELLM_PROXY_URL}/health")
            litellm_proxy = resp.status_code == 200
    except Exception:
        pass

    return {
        "status": "healthy",
        "version": "1.0.0",
        "providers": providers,
        "litellm_proxy": litellm_proxy,
    }
