from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

_api_key: str | None = None


def configure_api_key(key: str) -> None:
    global _api_key
    _api_key = key


async def verify_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> str:
    if _api_key is None:
        return "dev-mode"

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    if api_key != _api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key
