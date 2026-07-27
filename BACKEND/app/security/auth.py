"""Authentication dependency for API endpoints.

Supports multiple auth strategies in priority order:
1. Clerk JWT verification (when CLERK_JWKS_URL is configured) — production multi-user
2. Static API key (when FDE_API_KEY is set) — service-to-service / simple auth
3. Dev mode (when APP_ENV=development and no keys configured) — open access

Clerk JWTs are verified against the JWKS endpoint (public key fetched and cached).
The `sub` claim (Clerk user ID) becomes both `tenant_id` and `owner_id`, giving each
user their own isolated session namespace.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException, status

from app.config import settings

# Cache the JWKS client (fetches and caches public keys automatically)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not settings.clerk_jwks_url:
            raise ValueError("CLERK_JWKS_URL not configured")
        _jwks_client = PyJWKClient(
            settings.clerk_jwks_url,
            cache_keys=True,
            lifespan=3600,  # cache keys for 1 hour
        )
    return _jwks_client


@dataclass
class AuthContext:
    tenant_id: str
    owner_id: str
    token: str


def _verify_clerk_jwt(token: str) -> dict[str, Any]:
    """Verify a Clerk session JWT using the JWKS endpoint.

    Returns the decoded payload on success.
    Raises HTTPException on failure.
    """
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_nbf": True,
                "verify_aud": False,  # Clerk tokens don't always have aud
            },
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {e}",
        )


def _extract_tenant_from_token(token: str) -> dict[str, str]:
    """Extract tenant/owner identity from a bearer token.

    Tries strategies in order:
    1. Clerk JWKS verification (if configured)
    2. Static API key match
    3. Legacy JWT (HS256 with FDE_JWT_SECRET)
    4. Dev mode fallback
    """
    # Strategy 1: Clerk JWKS
    if settings.clerk_jwks_url:
        payload = _verify_clerk_jwt(token)
        user_id = payload.get("sub", "unknown")
        return {"tenant_id": user_id, "owner_id": user_id}

    # Strategy 2: Static API key (service-to-service)
    if settings.fde_api_key and token == settings.fde_api_key:
        return {"tenant_id": "api-key-user", "owner_id": "api-key-user"}

    # Strategy 3: Legacy HS256 JWT
    jwt_secret = settings.fde_jwt_secret
    if jwt_secret:
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            return {
                "tenant_id": payload.get("tenant_id", payload.get("sub", "unknown")),
                "owner_id": payload.get("owner_id", payload.get("sub", "unknown")),
            }
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )

    # Strategy 4: Dev mode (no auth configured)
    if settings.app_env.value == "development":
        # In dev, accept any token and try to decode it unverified to extract a user ID
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=["HS256", "RS256"],
            )
            user_id = payload.get("sub", payload.get("tenant_id", "dev-user"))
            return {"tenant_id": user_id, "owner_id": user_id}
        except jwt.InvalidTokenError:
            pass
        return {"tenant_id": "dev-tenant", "owner_id": "dev-user"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No authentication method configured",
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
