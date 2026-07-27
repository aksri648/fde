import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

router = APIRouter(prefix="/v1/jobs", tags=["websocket"])


@router.websocket("/{job_id}/events")
async def websocket_events(
    websocket: WebSocket,
    job_id: str,
) -> None:
    await websocket.accept()

    try:
        event_service = websocket.app.state.event_service

        snapshot = await event_service.get_snapshot(job_id)
        await websocket.send_json(
            {
                "type": "snapshot",
                "data": snapshot.model_dump(),
            }
        )

        queue = event_service.subscribe(job_id)

        try:
            while True:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    await websocket.send_json(
                        {
                            "type": "event",
                            "data": event_data,
                        }
                    )
                except TimeoutError:
                    await websocket.send_json({"type": "ping"})

                    try:
                        response = await asyncio.wait_for(
                            websocket.receive_text(), timeout=5.0
                        )
                        if response == "pong":
                            continue
                    except TimeoutError:
                        pass

        except WebSocketDisconnect:
            pass
        finally:
            event_service.unsubscribe(job_id, queue)

    except Exception:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011)
