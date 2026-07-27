"""Contract tests for LiteLLM gateway."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestLiteLLMConfig:
    def test_config_file_exists(self) -> None:
        from pathlib import Path

        config_path = Path(__file__).parent.parent.parent / "litellm_config.yaml"
        assert config_path.exists(), "litellm_config.yaml must exist"

    def test_config_has_model_alias(self) -> None:
        from pathlib import Path

        import yaml

        config_path = Path(__file__).parent.parent.parent / "litellm_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)

        model_list = config.get("model_list", [])
        assert len(model_list) > 0, "Model list must not be empty"

        aliases = [m.get("model_name") for m in model_list]
        assert "fde-claude" in aliases, "Must have fde-claude model alias"

    def test_config_uses_env_references(self) -> None:
        from pathlib import Path

        config_path = Path(__file__).parent.parent.parent / "litellm_config.yaml"
        with open(config_path) as f:
            content = f.read()

        assert "ANTHROPIC_API_KEY" in content or "os.environ" in content, (
            "Config must use environment variable references, not hardcoded secrets"
        )


class TestLitellmHealthClient:
    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        from app.clients.litellm_health_client import LitellmHealthClient

        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("app.clients.litellm_health_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)

            client = LitellmHealthClient()
            result = await client.check_health()

            assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        from app.clients.litellm_health_client import LitellmHealthClient

        with patch("app.clients.litellm_health_client.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

            client = LitellmHealthClient()
            result = await client.check_health()

            assert result["healthy"] is False


class TestDockerComposeLiteLLM:
    def test_litellm_service_defined(self) -> None:
        from pathlib import Path

        import yaml

        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        services = config.get("services", {})
        assert "litellm" in services, "litellm service must be defined in docker-compose.yml"

    def test_litellm_uses_config_volume(self) -> None:
        from pathlib import Path

        import yaml

        compose_path = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(compose_path) as f:
            config = yaml.safe_load(f)

        litellm_service = config["services"]["litellm"]
        volumes = litellm_service.get("volumes", [])
        volume_strs = [str(v) for v in volumes]
        assert any("litellm_config.yaml" in v for v in volume_strs), (
            "litellm service must mount litellm_config.yaml"
        )
