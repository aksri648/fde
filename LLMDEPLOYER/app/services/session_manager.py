import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from app.models.session import Session, UserRequirements
from app.models.chat import ChatMessage


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            status="created",
            messages=[],
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return self._sessions[session_id]

    def update_requirements(self, session_id: str, requirements: UserRequirements) -> None:
        session = self.get_session(session_id)
        session.requirements = requirements

    def update_status(self, session_id: str, status: str) -> None:
        session = self.get_session(session_id)
        session.status = status

    def add_message(self, session_id: str, message: ChatMessage) -> None:
        session = self.get_session(session_id)
        session.messages.append(message.model_dump())

    def get_messages(self, session_id: str) -> list[dict]:
        session = self.get_session(session_id)
        return session.messages

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())


session_manager = SessionManager()
