"""Unit tests for auth module."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.security.auth import _extract_tenant_from_token, get_auth_context


class TestExtractTenant:
    def test_dev_mode_no_api_key(self) -> None:
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "app.security.auth.settings",
                type(
                    "S",
                    (),
                    {"app_env": type("E", (), {"value": "development"})(), "fde_api_key": ""},
                )(),
            )
            result = _extract_tenant_from_token("any-token")
            assert result["tenant_id"] == "dev-tenant"

    def test_api_key_auth(self) -> None:
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "app.security.auth.settings",
                type(
                    "S",
                    (),
                    {
                        "app_env": type("E", (), {"value": "development"})(),
                        "fde_api_key": "test-key",
                    },
                )(),
            )
            result = _extract_tenant_from_token("test-key")
            assert result["tenant_id"] == "api-key-user"

    def test_invalid_token_raises(self) -> None:
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "app.security.auth.settings",
                type(
                    "S",
                    (),
                    {
                        "app_env": type("E", (), {"value": "production"})(),
                        "fde_api_key": "real-key",
                    },
                )(),
            )
            with pytest.raises(HTTPException) as exc_info:
                _extract_tenant_from_token("invalid-token")
            assert exc_info.value.status_code == 401


class TestGetAuthContext:
    @pytest.mark.asyncio
    async def test_missing_header(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context(authorization=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_scheme(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context(authorization="Basic abc")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_bearer_dev(self) -> None:
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "app.security.auth.settings",
                type(
                    "S",
                    (),
                    {"app_env": type("E", (), {"value": "development"})(), "fde_api_key": ""},
                )(),
            )
            ctx = await get_auth_context(authorization="Bearer test-token")
            assert ctx.tenant_id == "dev-tenant"
            assert ctx.owner_id == "dev-user"
