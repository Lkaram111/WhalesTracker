from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class BroadcastManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self._connections:
            return
        disconnected: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(ws)
            except Exception:
                disconnected.append(ws)
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self._connections.discard(ws)


broadcast_manager = BroadcastManager()
