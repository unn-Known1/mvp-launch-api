"""
Tests for WebSocket connection manager (ws_manager.py).
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import WebSocket

from ws_manager import ConnectionManager, manager


class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def setup_method(self):
        self.cm = ConnectionManager()

    def test_connect_adds_connection(self):
        ws = MagicMock(spec=WebSocket)
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws, "user-1"))
        assert "user-1" in self.cm._connections
        assert ws in self.cm._connections["user-1"]
        loop.close()

    def test_connect_accepts_websocket(self):
        ws = MagicMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws, "user-1"))
        ws.accept.assert_awaited_once()
        loop.close()

    def test_connect_multiple_sessions_for_same_user(self):
        ws1 = MagicMock(spec=WebSocket)
        ws2 = MagicMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws1, "user-1"))
        loop.run_until_complete(self.cm.connect(ws2, "user-1"))
        assert len(self.cm._connections["user-1"]) == 2
        loop.close()

    def test_disconnect_removes_connection(self):
        ws = MagicMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws, "user-1"))
        self.cm.disconnect(ws, "user-1")
        assert "user-1" not in self.cm._connections
        loop.close()

    def test_disconnect_only_removes_specific_connection(self):
        ws1 = MagicMock(spec=WebSocket)
        ws2 = MagicMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws1, "user-1"))
        loop.run_until_complete(self.cm.connect(ws2, "user-1"))
        self.cm.disconnect(ws1, "user-1")
        assert "user-1" in self.cm._connections
        assert ws2 in self.cm._connections["user-1"]
        assert ws1 not in self.cm._connections["user-1"]
        loop.close()

    def test_disconnect_noop_for_unknown_user(self):
        ws = MagicMock(spec=WebSocket)
        self.cm.disconnect(ws, "nonexistent")
        assert "nonexistent" not in self.cm._connections

    def test_disconnect_noop_for_unknown_connection(self):
        ws = MagicMock(spec=WebSocket)
        self.cm.disconnect(ws, "user-1")
        assert "user-1" not in self.cm._connections

    def test_broadcast_anomaly_sends_to_all_users(self):
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws1, "user-1"))
        loop.run_until_complete(self.cm.connect(ws2, "user-2"))
        anomaly_data = {"metric": "cpu_usage", "value": 95.0}
        loop.run_until_complete(
            self.cm.broadcast_anomaly(anomaly_data, ["user-1", "user-2"])
        )
        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_awaited_once()
        call_arg = ws1.send_text.await_args[0][0]
        assert "anomaly_detected" in call_arg
        assert "cpu_usage" in call_arg
        loop.close()

    def test_is_connected_returns_true(self):
        ws = MagicMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws, "user-1"))
        assert self.cm.is_connected("user-1") is True
        loop.close()

    def test_is_connected_returns_false(self):
        assert self.cm.is_connected("nonexistent") is False

    def test_is_connected_after_disconnect(self):
        ws = MagicMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws, "user-1"))
        self.cm.disconnect(ws, "user-1")
        assert self.cm.is_connected("user-1") is False
        loop.close()

    def test_send_to_user_skips_nonexistent(self):
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            self.cm.send_to_user("nonexistent", {"msg": "hello"})
        )
        loop.close()

    def test_send_to_user_sends_message(self):
        ws = AsyncMock(spec=WebSocket)
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws, "user-1"))
        loop.run_until_complete(
            self.cm.send_to_user("user-1", {"type": "test", "value": 42})
        )
        ws.send_text.assert_awaited_once()
        call_arg = ws.send_text.await_args[0][0]
        assert '"type": "test"' in call_arg
        assert '"value": 42' in call_arg
        loop.close()

    def test_send_to_user_removes_dead_connection(self):
        ws = AsyncMock(spec=WebSocket)
        ws.send_text.side_effect = Exception("Connection closed")
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.cm.connect(ws, "user-1"))
        loop.run_until_complete(
            self.cm.send_to_user("user-1", {"type": "test"})
        )
        assert "user-1" not in self.cm._connections
        loop.close()


class TestGlobalManager:
    """Tests for the global manager singleton."""

    def test_manager_is_singleton(self):
        assert isinstance(manager, ConnectionManager)

    def test_manager_starts_empty(self):
        assert manager._connections == {}
