from fastapi import WebSocket
import json

from app.services.session_manager import session_manager
from app.utils.logger import get_logger

logger = get_logger("connection_manager")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        if session_id in self.active_connections:
            self.active_connections[session_id] = [
                ws for ws in self.active_connections[session_id] if ws != websocket
            ]
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_to_session(self, session_id: str, message: dict) -> None:
        if session_id in self.active_connections:
            dead = []
            for ws in self.active_connections[session_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active_connections[session_id].remove(ws)

        from datetime import datetime, timezone
        from app.models.chat import ChatMessage

        msg_type = message.get("type", "agent_message")
        payload = message.get("payload", {})
        chat_message = ChatMessage(
            id=str(__import__("uuid").uuid4()),
            text=payload.get("text", payload.get("message", "")),
            sender="assistant" if msg_type == "agent_message" else "system",
            timestamp=datetime.now(timezone.utc),
            message_type=msg_type,
        )
        session_manager.add_message(session_id, chat_message)

    async def broadcast(self, message: dict) -> None:
        for session_id in list(self.active_connections.keys()):
            await self.send_to_session(session_id, message)


connection_manager = ConnectionManager()
