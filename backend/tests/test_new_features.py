import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
import os
import io
import warnings
from PIL import Image
import sys
from pathlib import Path

# Suppress warnings for clean test output
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", module="httplib2")
warnings.filterwarnings("ignore", module="google.generativeai")

# Ensure repository root is importable so "backend" package resolves in tests
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set environment variable
os.environ['FRONTEND_URL'] = 'http://localhost:5173'

# Mock magic module
mock_magic = MagicMock()
mock_magic.from_buffer.return_value = "image/jpeg"
sys.modules['magic'] = mock_magic

# Mock telegram
mock_telegram = MagicMock()
sys.modules['telegram'] = mock_telegram
sys.modules['telegram.ext'] = mock_telegram.ext

# Determine imports based on python path
try:
    from main import app
    MODULE_NAME = "main"
except ImportError:
    from backend.main import app
    MODULE_NAME = "backend.main"

client = TestClient(app)

# Manually set the http_client in state
app.state.http_client = AsyncMock()

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "1.0.0"
    assert "services" in data

@pytest.fixture
def mock_hf_service():
    # Patch the functions in the module where 'app' is defined
    with patch(f"{MODULE_NAME}.detect_illegal_parking_clip", new_callable=AsyncMock) as mock_parking, \
         patch(f"{MODULE_NAME}.detect_street_light_clip", new_callable=AsyncMock) as mock_light, \
         patch(f"{MODULE_NAME}.detect_fire_clip", new_callable=AsyncMock) as mock_fire, \
         patch(f"{MODULE_NAME}.detect_stray_animal_clip", new_callable=AsyncMock) as mock_animal, \
         patch(f"{MODULE_NAME}.detect_blocked_road_clip", new_callable=AsyncMock) as mock_block:

        mock_parking.return_value = [{"label": "illegally parked car", "confidence": 0.95}]
        mock_light.return_value = [{"label": "broken streetlight", "confidence": 0.95}]
        mock_fire.return_value = [{"label": "fire", "confidence": 0.95}]
        mock_animal.return_value = [{"label": "stray dog", "confidence": 0.95}]
        mock_block.return_value = [{"label": "fallen tree", "confidence": 0.95}]

        yield {
            "parking": mock_parking,
            "light": mock_light,
            "fire": mock_fire,
            "animal": mock_animal,
            "block": mock_block
        }

def create_dummy_image():
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100), color='red')
    image.save(file, 'jpeg')
    file.seek(0)
    return file

def test_detect_illegal_parking(mock_hf_service):
    img = create_dummy_image()
    files = {"image": ("test.jpg", img, "image/jpeg")}
    response = client.post("/api/detect-illegal-parking", files=files)
    assert response.status_code == 200
    assert response.json()["detections"][0]["label"] == "illegally parked car"

def test_detect_street_light(mock_hf_service):
    img = create_dummy_image()
    files = {"image": ("test.jpg", img, "image/jpeg")}
    response = client.post("/api/detect-street-light", files=files)
    assert response.status_code == 200
    assert response.json()["detections"][0]["label"] == "broken streetlight"

def test_detect_fire(mock_hf_service):
    img = create_dummy_image()
    files = {"image": ("test.jpg", img, "image/jpeg")}
    response = client.post("/api/detect-fire", files=files)
    assert response.status_code == 200
    assert response.json()["detections"][0]["label"] == "fire"

def test_detect_stray_animal(mock_hf_service):
    img = create_dummy_image()
    files = {"image": ("test.jpg", img, "image/jpeg")}
    response = client.post("/api/detect-stray-animal", files=files)
    assert response.status_code == 200
    assert response.json()["detections"][0]["label"] == "stray dog"

def test_detect_blocked_road(mock_hf_service):
    img = create_dummy_image()
    files = {"image": ("test.jpg", img, "image/jpeg")}
    response = client.post("/api/detect-blocked-road", files=files)
    assert response.status_code == 200
    assert response.json()["detections"][0]["label"] == "fallen tree"
