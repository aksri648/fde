from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    ANTHROPIC_API_KEY: str = ""
    LITELLM_PROXY_URL: str = "http://localhost:4000"
    LLMDEPLOYER_API_KEY: str = ""
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    AZURE_SUBSCRIPTION_ID: str = ""
    RUNPOD_API_KEY: str = ""
    MODAL_TOKEN_ID: str = ""
    MODAL_TOKEN_SECRET: str = ""
    NGC_API_KEY: str = ""
    HUGGING_FACE_HUB_TOKEN: str = ""
    SYSTEM_PROMPT_PATH: str = "system_prompt.txt"
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
