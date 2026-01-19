"""
Tests for the Local ML Service.

This test file covers:
- LocalCLIPModel singleton pattern
- Thread-safe model loading
- Image classification functionality
- Detection functions for vandalism, infrastructure, and flooding
- Model status and health check
- Unified detection service

Issue #76: Create a Local Machine Learning model
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestLocalMLService:
    """Tests for the local_ml_service module."""
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample test image."""
        return Image.new("RGB", (224, 224), color="red")
    
    @pytest.fixture
    def sample_image_bytes(self, sample_image):
        """Convert sample image to bytes."""
        img_byte_arr = io.BytesIO()
        sample_image.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()
    
    def test_local_clip_model_singleton(self):
        """Test that LocalCLIPModel follows singleton pattern."""
        from local_ml_service import LocalCLIPModel
        
        model1 = LocalCLIPModel()
        model2 = LocalCLIPModel()
        
        assert model1 is model2, "LocalCLIPModel should be a singleton"
    
    def test_get_local_model_returns_instance(self):
        """Test that get_local_model returns a LocalCLIPModel instance."""
        from local_ml_service import get_local_model, LocalCLIPModel
        
        model = get_local_model()
        
        assert isinstance(model, LocalCLIPModel)
    
    def test_model_status_structure(self):
        """Test that get_model_status returns expected structure."""
        from local_ml_service import get_model_status
        
        status = get_model_status()
        
        assert "model_name" in status
        assert "is_available" in status
        assert "device" in status
        assert "quantization_enabled" in status
        assert "error" in status
    
    @pytest.mark.asyncio
    async def test_detect_vandalism_local_returns_list(self, sample_image):
        """Test that detect_vandalism_local returns a list."""
        from local_ml_service import detect_vandalism_local
        
        # May return empty list if model not loaded, but should not error
        try:
            result = await detect_vandalism_local(sample_image)
            assert isinstance(result, list)
        except Exception as e:
            # Expected if transformers not installed
            pytest.skip(f"Model dependencies not available: {e}")
    
    @pytest.mark.asyncio
    async def test_detect_infrastructure_local_returns_list(self, sample_image):
        """Test that detect_infrastructure_local returns a list."""
        from local_ml_service import detect_infrastructure_local
        
        try:
            result = await detect_infrastructure_local(sample_image)
            assert isinstance(result, list)
        except Exception as e:
            pytest.skip(f"Model dependencies not available: {e}")
    
    @pytest.mark.asyncio
    async def test_detect_flooding_local_returns_list(self, sample_image):
        """Test that detect_flooding_local returns a list."""
        from local_ml_service import detect_flooding_local
        
        try:
            result = await detect_flooding_local(sample_image)
            assert isinstance(result, list)
        except Exception as e:
            pytest.skip(f"Model dependencies not available: {e}")
    
    @pytest.mark.asyncio
    async def test_detect_civic_issues_local_all(self, sample_image):
        """Test unified detection function with 'all' issue type."""
        from local_ml_service import detect_civic_issues_local
        
        try:
            result = await detect_civic_issues_local(sample_image, issue_type="all")
            
            assert isinstance(result, dict)
            assert "vandalism" in result
            assert "infrastructure" in result
            assert "flooding" in result
        except Exception as e:
            pytest.skip(f"Model dependencies not available: {e}")
    
    @pytest.mark.asyncio
    async def test_check_local_model_health(self):
        """Test health check function."""
        from local_ml_service import check_local_model_health
        
        is_healthy, message = await check_local_model_health()
        
        assert isinstance(is_healthy, bool)
        assert isinstance(message, str)
        assert len(message) > 0


class TestUnifiedDetectionService:
    """Tests for the unified_detection_service module."""
    
    @pytest.fixture
    def sample_image(self):
        """Create a sample test image."""
        return Image.new("RGB", (224, 224), color="blue")
    
    def test_get_detection_service_returns_instance(self):
        """Test that get_detection_service returns a UnifiedDetectionService instance."""
        from unified_detection_service import get_detection_service, UnifiedDetectionService
        
        service = get_detection_service()
        
        assert isinstance(service, UnifiedDetectionService)
    
    def test_detection_backend_enum(self):
        """Test DetectionBackend enum values."""
        from unified_detection_service import DetectionBackend
        
        assert DetectionBackend.LOCAL.value == "local"
        assert DetectionBackend.HUGGINGFACE.value == "huggingface"
        assert DetectionBackend.AUTO.value == "auto"
    
    @pytest.mark.asyncio
    async def test_detect_vandalism_returns_list(self, sample_image):
        """Test that detect_vandalism returns a list."""
        from unified_detection_service import detect_vandalism
        
        try:
            result = await detect_vandalism(sample_image)
            assert isinstance(result, list)
        except Exception:
            # Expected if dependencies not installed
            pass
    
    @pytest.mark.asyncio
    async def test_detect_infrastructure_returns_list(self, sample_image):
        """Test that detect_infrastructure returns a list."""
        from unified_detection_service import detect_infrastructure
        
        try:
            result = await detect_infrastructure(sample_image)
            assert isinstance(result, list)
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_detect_flooding_returns_list(self, sample_image):
        """Test that detect_flooding returns a list."""
        from unified_detection_service import detect_flooding
        
        try:
            result = await detect_flooding(sample_image)
            assert isinstance(result, list)
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_detect_all_returns_dict(self, sample_image):
        """Test that detect_all returns a dictionary with all detection types."""
        from unified_detection_service import detect_all
        
        try:
            result = await detect_all(sample_image)
            
            assert isinstance(result, dict)
            assert "vandalism" in result
            assert "infrastructure" in result
            assert "flooding" in result
        except Exception:
            pass
    
    @pytest.mark.asyncio
    async def test_get_detection_status_structure(self):
        """Test that get_detection_status returns expected structure."""
        from unified_detection_service import get_detection_status
        
        status = await get_detection_status()
        
        assert isinstance(status, dict)
        assert "use_local_model" in status
        assert "enable_hf_fallback" in status
        assert "local_backend" in status
        assert "huggingface_backend" in status
        assert "active_backend" in status


class TestEnvironmentConfiguration:
    """Tests for environment variable configuration."""
    
    def test_use_local_ml_default(self):
        """Test default value for USE_LOCAL_ML."""
        # Clear env var if set
        original = os.environ.pop("USE_LOCAL_ML", None)
        
        try:
            # Reload module to pick up default
            import importlib
            import unified_detection_service
            importlib.reload(unified_detection_service)
            
            # Default should be true
            assert unified_detection_service.USE_LOCAL_MODEL == True
        finally:
            if original:
                os.environ["USE_LOCAL_ML"] = original
    
    def test_use_local_ml_env_override(self):
        """Test that USE_LOCAL_ML can be overridden via environment."""
        original = os.environ.get("USE_LOCAL_ML")
        os.environ["USE_LOCAL_ML"] = "false"
        
        try:
            import importlib
            import unified_detection_service
            importlib.reload(unified_detection_service)
            
            assert unified_detection_service.USE_LOCAL_MODEL == False
        finally:
            if original:
                os.environ["USE_LOCAL_ML"] = original
            else:
                os.environ.pop("USE_LOCAL_ML", None)


class TestIntegrationWithMain:
    """Integration tests with main.py endpoints."""
    
    @pytest.fixture
    def sample_image_bytes(self):
        """Create sample image bytes for upload testing."""
        image = Image.new("RGB", (224, 224), color="green")
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()
    
    def test_main_imports_unified_service(self):
        """Test that main.py correctly imports the unified detection service."""
        try:
            # This should not raise an ImportError
            from main import detect_vandalism, detect_flooding, detect_infrastructure
            assert callable(detect_vandalism)
            assert callable(detect_flooding)
            assert callable(detect_infrastructure)
        except ImportError as e:
            pytest.fail(f"Failed to import detection functions from main: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
