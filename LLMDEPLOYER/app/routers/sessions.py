import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.session_manager import session_manager
from app.services.question_flow import compile_requirements
from app.services.agent_orchestrator import orchestrate_deployment
from app.security import verify_api_key

router = APIRouter()

# Keep strong references to background tasks so they are not garbage-collected
# mid-execution (see https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task).
_background_tasks: set[asyncio.Task] = set()


def _spawn_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class AnswersRequest(BaseModel):
    answers: dict


class MessageRequest(BaseModel):
    text: str


@router.post("/sessions")
async def create_session(_: str = Depends(verify_api_key)):
    session = session_manager.create_session()
    return {"session_id": session.session_id, "status": session.status}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, _: str = Depends(verify_api_key)):
    session = session_manager.get_session(session_id)
    return session.model_dump()


@router.post("/sessions/{session_id}/answers")
async def submit_answers(session_id: str, request: AnswersRequest, _: str = Depends(verify_api_key)):
    session_manager.get_session(session_id)
    requirements = compile_requirements(request.answers)
    session_manager.update_requirements(session_id, requirements)
    session_manager.update_status(session_id, "analyzing")
    _spawn_background(orchestrate_deployment(session_id))
    return {
        "status": "analyzing",
        "message": "Requirements received. Deployment analysis started. Connect via WebSocket at /api/ws/{session_id} for real-time updates, or poll GET /api/sessions/{session_id}/messages.",
    }


@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str, _: str = Depends(verify_api_key)):
    session = session_manager.get_session(session_id)
    return {
        "session_id": session.session_id,
        "status": session.status,
        "deployment_result": session.deployment_result,
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, after_index: int | None = None, _: str = Depends(verify_api_key)):
    session_manager.get_session(session_id)
    messages = session_manager.get_messages(session_id)
    if after_index is not None:
        messages = messages[after_index:]
    return {"messages": messages}


@router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, request: MessageRequest, _: str = Depends(verify_api_key)):
    session_manager.get_session(session_id)
    from datetime import datetime, timezone
    from app.models.chat import ChatMessage
    import uuid

    chat_message = ChatMessage(
        id=str(uuid.uuid4()),
        text=request.text,
        sender="user",
        timestamp=datetime.now(timezone.utc),
        message_type="agent_message",
    )
    session_manager.add_message(session_id, chat_message)
    return {"status": "received"}
