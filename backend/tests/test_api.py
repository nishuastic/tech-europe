"""
Tests for Call Bridge API
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.call_bridge import call_manager, CallStatus, CallSession
from unittest.mock import AsyncMock, patch

client = TestClient(app)

@pytest.mark.asyncio
async def test_initiate_call_flow():
    # Mock dependencies
    with patch("app.services.call_bridge.call_manager.initiate_call", new_callable=AsyncMock) as mock_initiate:
        mock_session = CallSession(
            call_id="test-123",
            user_message="Hello",
            target="caf",
            target_number="+33...",
            status=CallStatus.PENDING
        )
        mock_initiate.return_value = mock_session
        
        response = client.post("/api/v1/call/initiate", json={
            "message": "Hello",
            "target": "caf"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["call_id"] == "test-123"
        assert data["status"] == "pending"

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
