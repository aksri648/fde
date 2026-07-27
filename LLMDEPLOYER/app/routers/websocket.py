from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.session_manager import session_manager
from app.services.connection_manager import connection_manager
from app.security import _get_api_key

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Authenticate before accepting the connection. The API key is supplied via
    # the `token` query parameter (browsers cannot set custom WS headers).
    configured_key = _get_api_key()
    if configured_key:
        provided = websocket.query_params.get("token")
        if provided != configured_key:
            await websocket.close(code=4401, reason="Unauthorized")
            return

    try:
        session = session_manager.get_session(session_id)
    except Exception:
        await websocket.close(code=4004, reason="Session not found")
        return

    await connection_manager.connect(session_id, websocket)

    await websocket.send_json(
        {
            "type": "connected",
            "payload": {"session_id": session_id, "status": session.status},
        }
    )

    try:
        while True:
            data = await websocket.receive_text()
            import json

            try:
                message = json.loads(data)
                if message.get("type") == "user_message":
                    from datetime import datetime, timezone
                    from app.models.chat import ChatMessage
                    import uuid

                    chat_message = ChatMessage(
                        id=str(uuid.uuid4()),
                        text=message.get("text", ""),
                        sender="user",
                        timestamp=datetime.now(timezone.utc),
                        message_type="agent_message",
                    )
                    session_manager.add_message(session_id, chat_message)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        connection_manager.disconnect(session_id, websocket)
