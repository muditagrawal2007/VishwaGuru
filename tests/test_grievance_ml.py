import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import sys
import os

# Add root to sys.path
sys.path.append(os.getcwd())

from backend.grievance_classifier import get_grievance_classifier
from backend.main import app

@pytest.fixture
def client():
    # Create a mock for AsyncClient that handles context manager and async methods
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value.status_code = 200
    mock_client_instance.post.return_value.json.return_value = []

    # Mock aclose to be awaitable
    mock_client_instance.aclose = AsyncMock()

    # Mock lifespan events to prevent heavy initialization
    with patch("backend.main.create_all_ai_services") as mock_create, \
         patch("backend.main.initialize_ai_services") as mock_init, \
         patch("backend.main.run_bot") as mock_bot, \
         patch("backend.main.httpx.AsyncClient", return_value=mock_client_instance) as mock_http, \
         patch("backend.main.migrate_db"), \
         patch("backend.main.load_maharashtra_pincode_data"), \
         patch("backend.main.load_maharashtra_mla_data"):

        mock_create.return_value = (MagicMock(), MagicMock(), MagicMock())

        with TestClient(app) as client:
            yield client

def test_classifier_loading():
    classifier = get_grievance_classifier()
    # It might be None if file not found, but we ran the training script so it should be there.
    assert classifier.model is not None

def test_classifier_prediction():
    classifier = get_grievance_classifier()
    # Force reload just in case
    classifier.load_model()

    # "Dirty water coming from tap" -> Water (validated in script run)
    pred = classifier.predict("Dirty water coming from tap")
    assert pred == "Water"

    # "Potholes everywhere" -> Roads (validated logic)
    pred = classifier.predict("Potholes everywhere")
    assert pred == "Roads"

def test_endpoint(client):
    response = client.post("/api/classify-grievance", json={"text": "Street lights are broken"})
    assert response.status_code == 200
    data = response.json()
    assert "category" in data
    # "Street lights" -> Electricity
    assert data["category"] == "Electricity"
