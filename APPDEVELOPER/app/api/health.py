from fastapi import APIRouter

from app.domain.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadyResponse)
async def readiness_check() -> ReadyResponse:
    return ReadyResponse(
        database=True,
        configuration=True,
    )
