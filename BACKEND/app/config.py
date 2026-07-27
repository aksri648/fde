from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    development = "development"
    staging = "staging"
    production = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.development
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://fde_user:change_me@localhost:5432/fde_backend"
    redis_url: str = "redis://localhost:6379/0"
    fde_api_key: str = ""
    fde_jwt_secret: str = ""
    anthropic_api_key: str = ""
    fde_claude_model: str = "claude-sonnet-4-20250514"
    claude_agent_sdk_timeout_seconds: int = 90
    litellm_proxy_url: str = "http://localhost:4000"
    litellm_master_key: str = ""
    # Base URL for the Anthropic-format endpoint the planner talks to. Point this
    # at the LiteLLM proxy (which exposes an Anthropic-compatible /v1/messages
    # endpoint and translates to your OpenAI-compatible backend). The client
    # keeps speaking the Anthropic wire format; only the destination changes.
    anthropic_base_url: str = "https://api.anthropic.com"
    appdeveloper_base_url: str = "http://localhost:8001"
    appdeveloper_api_key: str = ""
    llmdeployer_base_url: str = "http://localhost:8002"
    llmdeployer_api_key: str = ""
    outbox_max_attempts: int = 5
    outbox_poll_seconds: float = 1.0
    request_max_bytes: int = 65536
    planner_mode: str = "real"
    redis_rate_limit_key_prefix: str = "fde:ratelimit:"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    @field_validator("app_env", mode="before")
    @classmethod
    def _coerce_app_env(cls, v: Any) -> AppEnv:
        if isinstance(v, AppEnv):
            return v
        return AppEnv(str(v))

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.production


settings = Settings()
