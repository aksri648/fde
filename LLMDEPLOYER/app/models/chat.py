from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class ChatMessage(BaseModel):
    id: str
    text: str
    sender: Literal["user", "assistant", "system"]
    timestamp: datetime
    message_type: Literal["agent_message", "status_update", "error", "deployment_complete"]


class WebSocketMessage(BaseModel):
    type: str
    payload: dict
