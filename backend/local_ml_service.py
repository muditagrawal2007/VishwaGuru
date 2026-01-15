"""
Local Machine Learning Service for Zero-Shot Image Classification.

This module provides a local alternative to the Hugging Face API for
image classification tasks including vandalism, infrastructure damage,
and flooding detection.

Features:
- Local CLIP model inference (no external API dependency)
- Model caching and lazy loading for efficient resource usage
- Thread-safe singleton pattern for model management
- Optional INT8 quantization for reduced memory footprint
- Consistent interface with the existing hf_service.py

Issue #76: Create a Local Machine Learning model
"""

import os
import io
import logging
import threading
from functools import lru_cache
from typing import List, Dict, Optional, Tuple
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread-safe model management
_model_lock = threading.Lock()
_model_instance = None
_processor_instance = None

# Configuration
USE_QUANTIZATION = os.environ.get("LOCAL_ML_QUANTIZE", "false").lower() == "true"
MODEL_NAME = os.environ.get("LOCAL_CLIP_MODEL", "openai/clip-vit-base-patch32")
DEVICE = os.environ.get("LOCAL_ML_DEVICE", "cpu")  # Options: "cpu", "cuda"


class LocalCLIPModel:
    """
    Thread-safe singleton wrapper for local CLIP model.
    
    This class handles:
    - Lazy loading of the CLIP model to avoid blocking startup
    - Thread-safe access to model and processor
    - Optional quantization for memory efficiency
    - Graceful fallback on import/load errors
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._model = None
        self._processor = None
        self._is_loaded = False
        self._load_error = None
        self._initialized = True
    
    def _load_model(self) -> bool:
        """
        Load the CLIP model and processor.
        
        Returns:
            bool: True if loading succeeded, False otherwise
        """
        if self._is_loaded:
            return True
        
        if self._load_error:
            return False
        
        try:
            logger.info(f"Loading local CLIP model: {MODEL_NAME}")
            
            # Import transformers (heavy import, done lazily)
            from transformers import CLIPProcessor, CLIPModel
            import torch
            
            # Load model and processor
            self._processor = CLIPProcessor.from_pretrained(MODEL_NAME)
            self._model = CLIPModel.from_pretrained(MODEL_NAME)
            
            # Move to device
            if DEVICE == "cuda" and torch.cuda.is_available():
                self._model = self._model.to("cuda")
                logger.info("Model loaded on CUDA")
            else:
                self._model = self._model.to("cpu")
                logger.info("Model loaded on CPU")
            
            # Optional quantization for memory efficiency
            if USE_QUANTIZATION:
                try:
                    logger.info("Applying INT8 quantization...")
                    self._model = torch.quantization.quantize_dynamic(
                        self._model,
                        {torch.nn.Linear},
                        dtype=torch.qint8
                    )
                    logger.info("INT8 quantization applied successfully")
                except Exception as e:
                    logger.warning(f"Quantization failed (continuing with full precision): {e}")
            
            # Set to evaluation mode
            self._model.eval()
            
            self._is_loaded = True
            logger.info("Local CLIP model loaded successfully")
            return True
            
        except ImportError as e:
            self._load_error = f"Missing dependency: {e}. Install with: pip install transformers torch"
            logger.error(self._load_error)
            return False
        except Exception as e:
            self._load_error = f"Failed to load local CLIP model: {e}"
            logger.error(self._load_error, exc_info=True)
            return False
    
    def classify_image(
        self,
        image: Image.Image,
        candidate_labels: List[str],
        threshold: float = 0.0
    ) -> List[Dict]:
        """
        Perform zero-shot image classification using local CLIP model.
        
        Args:
            image: PIL Image to classify
            candidate_labels: List of text labels to match against
            threshold: Minimum confidence score to include in results
            
        Returns:
            List of dictionaries with 'label' and 'score' keys,
            sorted by score descending
        """
        with self._lock:
            if not self._load_model():
                logger.warning("Model not available, returning empty results")
                return []
        
        try:
            import torch
            
            # Preprocess inputs
            inputs = self._processor(
                text=candidate_labels,
                images=image,
                return_tensors="pt",
                padding=True
            )
            
            # Move inputs to device
            device = next(self._model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            # Run inference
            with torch.no_grad():
                outputs = self._model(**inputs)
            
            # Calculate similarity scores
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)
            
            # Convert to list of results
            probs_list = probs.cpu().numpy()[0].tolist()
            
            results = []
            for label, score in zip(candidate_labels, probs_list):
                if score >= threshold:
                    results.append({
                        "label": label,
                        "score": float(score)
                    })
            
            # Sort by score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Classification error: {e}", exc_info=True)
            return []
    
    @property
    def is_available(self) -> bool:
        """Check if the model is loaded and available."""
        return self._is_loaded
    
    @property
    def error_message(self) -> Optional[str]:
        """Get the error message if loading failed."""
        return self._load_error


# Global model instance (created lazily)
def get_local_model() -> LocalCLIPModel:
    """Get the singleton LocalCLIPModel instance."""
    return LocalCLIPModel()


async def detect_vandalism_local(image: Image.Image) -> List[Dict]:
    """
    Detects vandalism/graffiti using local Zero-Shot Image Classification with CLIP.
    
    This is a drop-in replacement for detect_vandalism_clip from hf_service.py
    
    Args:
        image: PIL Image to analyze
        
    Returns:
        List of detected vandalism items with 'label', 'confidence', and 'box' keys
    """
    try:
        labels = [
            "graffiti",
            "vandalism", 
            "spray paint",
            "street art",
            "clean wall",
            "public property",
            "normal street"
        ]
        
        model = get_local_model()
        results = model.classify_image(image, labels, threshold=0.0)
        
        # Filter for vandalism-related labels with high confidence
        vandalism_labels = ["graffiti", "vandalism", "spray paint"]
        detected = []
        
        for res in results:
            if res.get("label") in vandalism_labels and res.get("score", 0) > 0.4:
                detected.append({
                    "label": res["label"],
                    "confidence": res["score"],
                    "box": []  # CLIP doesn't provide bounding boxes
                })
        
        return detected
        
    except Exception as e:
        logger.error(f"Local vandalism detection error: {e}", exc_info=True)
        return []


async def detect_infrastructure_local(image: Image.Image) -> List[Dict]:
    """
    Detects infrastructure damage using local Zero-Shot Image Classification with CLIP.
    
    This is a drop-in replacement for detect_infrastructure_clip from hf_service.py
    
    Args:
        image: PIL Image to analyze
        
    Returns:
        List of detected infrastructure damage with 'label', 'confidence', and 'box' keys
    """
    try:
        labels = [
            "broken streetlight",
            "damaged traffic sign",
            "fallen tree",
            "damaged fence",
            "pothole",
            "clean street",
            "normal infrastructure"
        ]
        
        model = get_local_model()
        results = model.classify_image(image, labels, threshold=0.0)
        
        # Filter for damage-related labels with high confidence
        damage_labels = ["broken streetlight", "damaged traffic sign", "fallen tree", "damaged fence"]
        detected = []
        
        for res in results:
            if res.get("label") in damage_labels and res.get("score", 0) > 0.4:
                detected.append({
                    "label": res["label"],
                    "confidence": res["score"],
                    "box": []
                })
        
        return detected
        
    except Exception as e:
        logger.error(f"Local infrastructure detection error: {e}", exc_info=True)
        return []


async def detect_flooding_local(image: Image.Image) -> List[Dict]:
    """
    Detects flooding/waterlogging using local Zero-Shot Image Classification with CLIP.
    
    This is a drop-in replacement for detect_flooding_clip from hf_service.py
    
    Args:
        image: PIL Image to analyze
        
    Returns:
        List of detected flooding with 'label', 'confidence', and 'box' keys
    """
    try:
        labels = [
            "flooded street",
            "waterlogging",
            "blocked drain",
            "heavy rain",
            "dry street",
            "normal road"
        ]
        
        model = get_local_model()
        results = model.classify_image(image, labels, threshold=0.0)
        
        # Filter for flooding-related labels with high confidence
        flooding_labels = ["flooded street", "waterlogging", "blocked drain", "heavy rain"]
        detected = []
        
        for res in results:
            if res.get("label") in flooding_labels and res.get("score", 0) > 0.4:
                detected.append({
                    "label": res["label"],
                    "confidence": res["score"],
                    "box": []
                })
        
        return detected
        
    except Exception as e:
        logger.error(f"Local flooding detection error: {e}", exc_info=True)
        return []


# Unified detection function for multi-label classification
async def detect_civic_issues_local(
    image: Image.Image,
    issue_type: str = "all"
) -> Dict[str, List[Dict]]:
    """
    Unified detection function for all civic issue types.
    
    Args:
        image: PIL Image to analyze
        issue_type: One of "vandalism", "infrastructure", "flooding", or "all"
        
    Returns:
        Dictionary mapping issue type to list of detections
    """
    results = {}
    
    if issue_type in ("vandalism", "all"):
        results["vandalism"] = await detect_vandalism_local(image)
    
    if issue_type in ("infrastructure", "all"):
        results["infrastructure"] = await detect_infrastructure_local(image)
    
    if issue_type in ("flooding", "all"):
        results["flooding"] = await detect_flooding_local(image)
    
    return results


def get_model_status() -> Dict:
    """
    Get the current status of the local ML model.
    
    Returns:
        Dictionary with model status information
    """
    model = get_local_model()
    
    return {
        "model_name": MODEL_NAME,
        "is_available": model.is_available,
        "device": DEVICE,
        "quantization_enabled": USE_QUANTIZATION,
        "error": model.error_message
    }


# Health check function for API integration
async def check_local_model_health() -> Tuple[bool, str]:
    """
    Check if the local ML model is healthy and ready.
    
    Returns:
        Tuple of (is_healthy, status_message)
    """
    try:
        model = get_local_model()
        
        if model.is_available:
            return True, "Local ML model is ready"
        elif model.error_message:
            return False, f"Model error: {model.error_message}"
        else:
            # Try to load the model
            test_image = Image.new("RGB", (224, 224), color="white")
            results = model.classify_image(test_image, ["test"], threshold=0.0)
            
            if model.is_available:
                return True, "Local ML model initialized and ready"
            else:
                return False, "Model initialization failed"
                
    except Exception as e:
        return False, f"Health check failed: {e}"
