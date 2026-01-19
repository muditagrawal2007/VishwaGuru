"""
DEPRECATED: This module is no longer used.
Please use local_ml_service.py for local ML model-based detection instead of Hugging Face API.

This file is kept for reference purposes only.
"""
import os
import io
import httpx
import base64
from typing import Union, List, Dict, Any
from PIL import Image
import asyncio
import logging

logger = logging.getLogger(__name__)

# HF_TOKEN is optional for public models but recommended for higher limits
token = os.environ.get("HF_TOKEN")
headers = {"Authorization": f"Bearer {token}"} if token else {}
API_URL = "https://api-inference.huggingface.co/models/openai/clip-vit-base-patch32"
CAPTION_API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"

async def query_hf_api(image_bytes, labels, client=None):
    """
    Queries Hugging Face API using a shared or new HTTP client.
    """
    if client:
        return await _make_request(client, image_bytes, labels)

    async with httpx.AsyncClient() as new_client:
        return await _make_request(new_client, image_bytes, labels)

async def _make_request(client, image_bytes, labels):
    try:
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        payload = {
            "inputs": image_base64,
            "parameters": {
                "candidate_labels": labels
            }
        }

        response = await client.post(API_URL, headers=headers, json=payload, timeout=20.0)
        if response.status_code != 200:
            logger.error(f"HF API Error: {response.status_code} - {response.text}")
            return []
        return response.json()
    except Exception as e:
        logger.error(f"HF API Request Exception: {e}")
        return []

def _prepare_image_bytes(image: Union[Image.Image, bytes]) -> bytes:
    """
    Helper to get bytes from PIL Image or return bytes as is.
    Avoids unnecessary re-encoding if bytes are already available.
    """
    if isinstance(image, bytes):
        return image

    img_byte_arr = io.BytesIO()
    # If image.format is not available (e.g. newly created image), default to JPEG
    fmt = image.format if image.format else 'JPEG'
    image.save(img_byte_arr, format=fmt)
    return img_byte_arr.getvalue()

async def generate_image_caption(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    """
    Generates a description for the image using Salesforce BLIP model.
    """
    try:
        img_bytes = _prepare_image_bytes(image)
        image_base64 = base64.b64encode(img_bytes).decode('utf-8')

        payload = {
            "inputs": image_base64
        }

        async def _make_caption_request(c):
             response = await c.post(CAPTION_API_URL, headers=headers, json=payload, timeout=20.0)
             if response.status_code != 200:
                 logger.error(f"HF Caption API Error: {response.status_code} - {response.text}")
                 return None
             return response.json()

        if client:
            result = await _make_caption_request(client)
        else:
            async with httpx.AsyncClient() as new_client:
                result = await _make_caption_request(new_client)

        # Result format for image-to-text is usually [{"generated_text": "a dog ..."}]
        if isinstance(result, list) and len(result) > 0 and 'generated_text' in result[0]:
            return result[0]['generated_text']
        return None

    except Exception as e:
        logger.error(f"HF Caption Generation Error: {e}")
        return None

async def _detect_clip_generic(image: Union[Image.Image, bytes], labels: List[str], target_labels: List[str], client: httpx.AsyncClient = None) -> List[Dict]:
    try:
        img_bytes = _prepare_image_bytes(image)
        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        detected = []
        for res in results:
            if isinstance(res, dict) and res.get('label') in target_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_vandalism_clip(image, client=None):
    labels = ["graffiti", "vandalism", "spray paint", "street art", "clean wall", "public property", "normal street"]
    targets = ["graffiti", "vandalism", "spray paint"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_pest_clip(image, client=None):
    labels = ["rat", "mouse", "cockroach", "pest infestation", "garbage", "clean room", "street"]
    targets = ["rat", "mouse", "cockroach", "pest infestation"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_infrastructure_clip(image, client=None):
    labels = ["broken streetlight", "damaged traffic sign", "fallen tree", "damaged fence", "pothole", "clean street", "normal infrastructure"]
    targets = ["broken streetlight", "damaged traffic sign", "fallen tree", "damaged fence"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_flooding_clip(image, client=None):
    labels = ["flooded street", "waterlogging", "blocked drain", "heavy rain", "dry street", "normal road"]
    targets = ["flooded street", "waterlogging", "blocked drain", "heavy rain"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_illegal_parking_clip(image, client=None):
    labels = ["illegal parking", "car on sidewalk", "blocked driveway", "parked in no parking zone", "legal parking", "empty street"]
    targets = ["illegal parking", "car on sidewalk", "blocked driveway", "parked in no parking zone"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_street_light_clip(image, client=None):
    labels = ["broken streetlight", "street light off", "dark street", "working streetlight", "daytime"]
    targets = ["broken streetlight", "street light off", "dark street"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_fire_clip(image, client=None):
    labels = ["fire", "smoke", "burning", "flames", "normal", "fog"]
    targets = ["fire", "smoke", "burning", "flames"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_stray_animal_clip(image, client=None):
    labels = ["stray dog", "stray cow", "stray cattle", "monkey", "animal hazard", "pet dog", "no animals"]
    targets = ["stray dog", "stray cow", "stray cattle", "monkey", "animal hazard"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_blocked_road_clip(image, client=None):
    labels = ["blocked road", "road block", "fallen tree", "construction", "clear road", "traffic"]
    targets = ["blocked road", "road block", "fallen tree", "construction"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_tree_hazard_clip(image, client=None):
    labels = ["fallen tree", "leaning tree", "broken branch", "healthy tree"]
    targets = ["fallen tree", "leaning tree", "broken branch"]
    return await _detect_clip_generic(image, labels, targets, client)

async def detect_severity_clip(image, client=None):
    labels = ["critical severity", "high severity", "medium severity", "low severity", "normal"]
    # Logic might differ, returning single label
    # For now reusing generic
    results = await _detect_clip_generic(image, labels, labels, client)
    # Extract top result
    if results:
        top = max(results, key=lambda x: x['confidence'])
        return {"level": top['label'].split()[0].title(), "confidence": top['confidence'], "raw_label": top['label']}
    return {"level": "Low", "confidence": 0.0, "raw_label": "normal"}

async def detect_smart_scan_clip(image, client=None):
    # This likely expects returning a category
    labels = ["pothole", "garbage", "flooding", "vandalism", "fire", "accident", "normal"]
    targets = labels[:-1]
    results = await _detect_clip_generic(image, labels, targets, client)
    return {"detections": results}
