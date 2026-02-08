"""
Tests for Call Bridge API
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch

client = TestClient(app)


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_initiate_call_flow():
    # Mock TwilioService
    with patch("app.api.v1.call_websocket.TwilioService") as MockTwilioService:
        # Configure mock instance
        mock_instance = MockTwilioService.return_value
        mock_instance.initiate_media_stream_call.return_value = "CA12345"

        # Test the endpoint
        response = client.post(
            "/api/v1/call/initiate", json={"message": "Hello", "target": "caf"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert data["status"] == "calling"
        assert "I'm now calling CAF" in data["message"]
        assert "call_action" in data
        assert data["call_action"]["target"] == "caf"
        assert "call_id" in data["call_action"]


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
