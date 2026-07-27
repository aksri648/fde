"""Authentication dependency for API endpoints."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, status

from app.config import settings


@dataclass
class AuthContext:
    tenant_id: str
    owner_id: str
    token: str


def _extract_tenant_from_token(token: str) -> dict[str, str]:
    if settings.app_env.value == "development" and settings.fde_api_key == "":
        return {"tenant_id": "dev-tenant", "owner_id": "dev-user"}

    if settings.fde_api_key and token == settings.fde_api_key:
        return {"tenant_id": "api-key-user", "owner_id": "api-key-user"}

    try:
        jwt_secret = getattr(settings, "fde_jwt_secret", "")
        if jwt_secret:
            # Verified path: signature is checked against the configured secret.
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        elif settings.app_env.value == "development":
            # Development convenience only: accept unverified tokens when no
            # signing secret is configured.
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["HS256", "RS256"],
            )
        else:
            # Staging/production without a configured secret must not accept
            # unverified JWTs — doing so would allow tenant impersonation.
            raise jwt.InvalidTokenError("JWT verification is not configured")
        return {
            "tenant_id": payload.get("tenant_id", payload.get("sub", "unknown")),
            "owner_id": payload.get("owner_id", payload.get("sub", "unknown")),
        }
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


async def get_auth_context(
    authorization: str | None = Header(default=None),
) -> AuthContext:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization scheme, expected 'Bearer <token>'",
        )

    claims = _extract_tenant_from_token(token)
    return AuthContext(
        tenant_id=claims["tenant_id"],
        owner_id=claims["owner_id"],
        token=token,
    )
