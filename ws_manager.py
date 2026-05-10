"""
WebSocket connection manager for real-time anomaly alerts.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections per user with async lock for thread-safety."""

    def __init__(self) -> None:
        # user_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept and register a WebSocket connection for a user."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove a WebSocket connection for a user (async for thread-safety)."""
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]

    async def send_to_user(self, user_id: str, data: dict[str, Any]) -> None:
        """Send JSON data to all connections of a specific user."""
        async with self._lock:
            if user_id not in self._connections:
                return
            message = json.dumps(data, default=str)
            dead: list[WebSocket] = []
            for ws in self._connections[user_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections[user_id].discard(ws)
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def broadcast_anomaly(
        self, anomaly_data: dict[str, Any], user_ids: list[str]
    ) -> None:
        """Broadcast an anomaly event to all specified users."""
        payload = {
            "type": "anomaly_detected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "anomaly": anomaly_data,
        }
        for uid in user_ids:
            await self.send_to_user(uid, payload)

    def is_connected(self, user_id: str) -> bool:
        """Check if a user has any active connections."""
        return bool(self._connections.get(user_id))


manager = ConnectionManager()