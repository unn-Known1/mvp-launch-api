"""
Integration tests for WebSocket anomaly notifications.

Tests WebSocket connection lifecycle with JWT auth and verifies
anomaly detection events are pushed to connected clients.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-ws-testing"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/nonexistent"

import jwt
import pytest
from starlette.testclient import TestClient

from auth import create_access_token
from main import app
from ws_manager import ConnectionManager, manager as global_manager


def test_websocket_connect_with_valid_token():
    token = create_access_token("test-user-id")
    with TestClient(app).websocket_connect(
        f"/api/v1/anomalies/ws/anomalies?token={token}"
    ) as ws:
        assert global_manager.is_connected("test-user-id")


def test_websocket_rejects_invalid_token():
    bad_token = jwt.encode(
        {"sub": "test", "type": "access", "exp": 9999999999},
        "wrong-secret",
        algorithm="HS256",
    )
    with pytest.raises(Exception):
        with TestClient(app).websocket_connect(
            f"/api/v1/anomalies/ws/anomalies?token={bad_token}"
        ):
            pass


def test_websocket_rejects_refresh_token():
    token = jwt.encode(
        {"sub": "test-user", "type": "refresh", "exp": 9999999999},
        os.environ["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    with pytest.raises(Exception):
        with TestClient(app).websocket_connect(
            f"/api/v1/anomalies/ws/anomalies?token={token}"
        ):
            pass


def test_websocket_connect_cleans_up_on_disconnect():
    token = create_access_token("test-disconnect-user")
    with TestClient(app).websocket_connect(
        f"/api/v1/anomalies/ws/anomalies?token={token}"
    ) as ws:
        assert global_manager.is_connected("test-disconnect-user")
    assert not global_manager.is_connected("test-disconnect-user")


@pytest.mark.asyncio
async def test_websocket_anomaly_broadcast_reaches_client():
    token = create_access_token("broadcast-test-user")
    with TestClient(app).websocket_connect(
        f"/api/v1/anomalies/ws/anomalies?token={token}"
    ) as ws:
        assert global_manager.is_connected("broadcast-test-user")

        anomaly_data = {
            "id": "test-id",
            "dataset_id": "ds-1",
            "metric_name": "cpu_usage",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "expected_value": "50.0",
            "actual_value": "95.0",
            "severity": "high",
            "detection_method": "z_score",
            "status": "flagged",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await global_manager.broadcast_anomaly(anomaly_data, ["broadcast-test-user"])

        response = ws.receive_text()
        assert "anomaly_detected" in response
        assert "cpu_usage" in response
        assert "high" in response
