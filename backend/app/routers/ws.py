from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..db import SessionLocal
from ..models import User
from ..security import decode_token
from ..services.realtime import hub

router = APIRouter()


@router.websocket("/ws")
async def websocket(ws: WebSocket, token: str):
    """Live events: request.analyzed, request.new, quote.*, message.new, job.*"""
    uid = decode_token(token)
    db = SessionLocal()
    try:
        user = db.get(User, uid) if uid else None
    finally:
        db.close()
    if user is None:
        await ws.close(code=4401)
        return
    await hub.connect(user.id, ws)
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(user.id, ws)
