import json

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("system_prompt")


def load_system_prompt() -> str:
    settings = get_settings()
    try:
        with open(settings.SYSTEM_PROMPT_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "You are LLMDeployer, an expert at analyzing LLM deployment requirements and selecting the optimal deployment strategy. Analyze the user's requirements and execute the deployment using the available tools."
