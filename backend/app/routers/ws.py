import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..db import SessionLocal
from ..deps import user_from_token
from ..services.realtime import hub

router = APIRouter()
AUTH_TIMEOUT_S = 10


@router.websocket("/ws")
async def websocket(ws: WebSocket):
    """Live events: request.analyzed, request.new, quote.*, message.new, job.*, workshop.verification

    The client authenticates with its first message, {"token": "<jwt>"}, so the token
    never appears in URLs or proxy access logs.
    """
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=AUTH_TIMEOUT_S)
        token = first.get("token") if isinstance(first, dict) else None
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError, KeyError):
        await ws.close(code=4401)
        return
    db = SessionLocal()
    try:
        user = user_from_token(db, token) if isinstance(token, str) else None
    finally:
        db.close()
    if user is None:
        await ws.close(code=4401)
        return
    hub.register(user.id, ws)
    await ws.send_json({"type": "ready"})
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(user.id, ws)
