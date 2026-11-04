"""In-process WebSocket hub plus Expo push notifications.

For several API instances put Redis pub/sub behind `broadcast`; the interface stays the same.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

import httpx
from fastapi import WebSocket

from ..config import get_settings

log = logging.getLogger("dentbid.realtime")
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class Hub:
    def __init__(self) -> None:
        self.sockets: dict[int, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def register(self, user_id: int, ws: WebSocket) -> None:
        """Adds an already accepted and authenticated socket."""
        self.loop = asyncio.get_running_loop()
        self.sockets[user_id].add(ws)

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        self.sockets[user_id].discard(ws)

    async def _send(self, user_id: int, event: dict) -> None:
        for ws in list(self.sockets.get(user_id, ())):
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(user_id, ws)

    def notify(self, user_ids, event: dict) -> None:
        """Thread-safe: callable from request handlers and background workers."""
        if self.loop is None or self.loop.is_closed():
            return
        for uid in set(user_ids):
            if self.sockets.get(uid):
                asyncio.run_coroutine_threadsafe(self._send(uid, event), self.loop)


hub = Hub()


def send_push(tokens: list[str], title: str, body: str, data: dict | None = None) -> None:
    tokens = [t for t in tokens if t and t.startswith("ExponentPushToken")]
    if not tokens:
        return
    headers = {"Content-Type": "application/json"}
    token = get_settings().expo_access_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    msgs = [{"to": t, "title": title, "body": body, "data": data or {}, "sound": "default"} for t in tokens]
    try:
        for i in range(0, len(msgs), 100):
            httpx.post(EXPO_PUSH_URL, json=msgs[i:i + 100], headers=headers, timeout=10)
    except httpx.HTTPError as e:
        log.warning("push failed: %s", e)


def notify_users(users, event: dict, title: str | None = None, body: str | None = None) -> None:
    """WebSocket event to everyone online, push notification to everyone with a token."""
    users = [u for u in users if u is not None]
    hub.notify([u.id for u in users], event)
    if title:
        send_push([u.push_token for u in users if u.push_token], title, body or "", event)
