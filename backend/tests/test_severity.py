import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from main import app

@pytest.mark.asyncio
async def test_detect_severity_endpoint():
    # Mock AI services initialization to prevent startup failure
    with patch('main.create_all_ai_services') as mock_create_services, \
         patch('main.initialize_ai_services') as mock_init_services, \
         patch('main.detect_severity_clip', new_callable=AsyncMock) as mock_detect:

        # Setup mocks
        mock_create_services.return_value = (MagicMock(), MagicMock(), MagicMock())

        # Define the mock return value for detection
        mock_detect.return_value = {
            "level": "Critical",
            "raw_label": "critical emergency",
            "confidence": 0.95
        }

        # Create a dummy image file
        file_content = b"fake image content"
        files = {"image": ("test.jpg", file_content, "image/jpeg")}

        # Use TestClient as context manager to trigger lifespan (startup/shutdown)
        with TestClient(app) as client:
            # Call the endpoint
            response = client.post("/api/detect-severity", files=files)

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["level"] == "Critical"
            assert data["raw_label"] == "critical emergency"
            assert data["confidence"] == 0.95

            # Verify the mock was called
            mock_detect.assert_called_once()
