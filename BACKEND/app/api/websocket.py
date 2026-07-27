"""WebSocket endpoint for real-time event streaming."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.db.session import async_session_factory
from app.repositories.session_repository import SessionRepository
from app.security.auth import _extract_tenant_from_token
from app.services.event_service import event_broadcaster

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/v1/sessions/{session_id}/events")
async def session_events(
    websocket: WebSocket,
    session_id: str,
    after_sequence: int = Query(default=0),
    token: str = Query(default=""),
) -> None:
    await websocket.accept()

    try:
        claims = _extract_tenant_from_token(token)
        tenant_id = claims["tenant_id"]
    except Exception:
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=4001)
        return

    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        await websocket.send_json({"error": "Invalid session_id"})
        await websocket.close(code=4002)
        return

    async with async_session_factory() as db:
        repo = SessionRepository(db)
        session = await repo.get_by_id_for_tenant(sid, tenant_id)
        if session is None:
            await websocket.send_json({"error": "Session not found or access denied"})
            await websocket.close(code=4003)
            return

    sequence, queue = event_broadcaster.subscribe(session_id)

    history = event_broadcaster.get_history_after(session_id, after_sequence)
    if history:
        for event in history:
            await websocket.send_json(event)

    snapshot = {
        "sequence": 0,
        "event": "snapshot",
        "data": {
            "session_id": session_id,
            "state": session.state,
            "plan_version": session.current_plan_version,
        },
    }
    await websocket.send_json(snapshot)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event)
            except TimeoutError:
                ping = {"sequence": 0, "event": "ping", "data": {}}
                await websocket.send_json(ping)
    except WebSocketDisconnect:
        pass
    finally:
        event_broadcaster.unsubscribe(session_id, sequence)
