"""
DEPRECATED: This module is no longer used.
Please use local_ml_service.py for local ML model-based detection instead of Hugging Face API.

This file is kept for reference purposes only.
"""
import os
import io
import httpx
from PIL import Image
import asyncio
from typing import Union
import logging
import base64

# Configure logger
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
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    payload = {
        "inputs": image_base64,
        "parameters": {
            "candidate_labels": labels
        }
    }

    try:
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

async def detect_vandalism_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    """
    Detects vandalism/graffiti using Zero-Shot Image Classification with CLIP (Async).
    """
    try:
        labels = ["graffiti", "vandalism", "spray paint", "street art", "clean wall", "public property", "normal street"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        # Results format: [{'label': 'graffiti', 'score': 0.9}, ...]
        if not isinstance(results, list):
             return []

        vandalism_labels = ["graffiti", "vandalism", "spray paint"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in vandalism_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_severity_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["critical emergency", "hazardous", "urgent repair needed", "minor issue", "safe", "normal"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
            return {"label": "unknown", "score": 0}

        # Sort by score descending
        results.sort(key=lambda x: x.get('score', 0), reverse=True)

        top_result = results[0] if results else {"label": "unknown", "score": 0}

        # Map labels to standardized severity levels
        severity_map = {
            "critical emergency": "Critical",
            "hazardous": "High",
            "urgent repair needed": "High",
            "minor issue": "Medium",
            "safe": "Low",
            "normal": "Low"
        }

        return {
            "level": severity_map.get(top_result['label'], "Medium"),
            "raw_label": top_result['label'],
            "confidence": top_result['score']
        }
    except Exception as e:
        print(f"HF Severity Detection Error: {e}")
        return {"level": "Unknown", "error": str(e)}

async def detect_tree_hazard_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["fallen tree", "dangling branch", "leaning tree", "overgrown vegetation", "healthy tree", "normal street"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        tree_labels = ["fallen tree", "dangling branch", "leaning tree", "overgrown vegetation"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in tree_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_pest_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["rat", "mouse", "cockroach", "pest infestation", "garbage", "clean room", "street"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        pest_labels = ["rat", "mouse", "cockroach", "pest infestation"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in pest_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_infrastructure_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["broken streetlight", "damaged traffic sign", "fallen tree", "damaged fence", "pothole", "clean street", "normal infrastructure"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        damage_labels = ["broken streetlight", "damaged traffic sign", "fallen tree", "damaged fence"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in damage_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_flooding_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["flooded street", "waterlogging", "blocked drain", "heavy rain", "dry street", "normal road"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        flooding_labels = ["flooded street", "waterlogging", "blocked drain", "heavy rain"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in flooding_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_illegal_parking_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["illegally parked car", "car blocking driveway", "car on sidewalk", "double parking", "parked car", "empty street", "traffic jam"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        parking_labels = ["illegally parked car", "car blocking driveway", "car on sidewalk", "double parking"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in parking_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_street_light_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["broken streetlight", "dark street", "street light off", "working streetlight", "daytime street"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        light_labels = ["broken streetlight", "dark street", "street light off"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in light_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_fire_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["fire", "smoke", "flames", "forest fire", "building fire", "normal street", "clear sky"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        fire_labels = ["fire", "smoke", "flames", "forest fire", "building fire"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in fire_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_stray_animal_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["stray dog", "stray cow", "stray cattle", "wild animal", "pet dog", "empty street"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        animal_labels = ["stray dog", "stray cow", "stray cattle", "wild animal"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in animal_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []

async def detect_blocked_road_clip(image: Union[Image.Image, bytes], client: httpx.AsyncClient = None):
    try:
        labels = ["fallen tree", "construction work", "road barrier", "traffic accident", "landslide", "clear road", "normal traffic"]

        img_bytes = _prepare_image_bytes(image)

        results = await query_hf_api(img_bytes, labels, client=client)

        if not isinstance(results, list):
             return []

        block_labels = ["fallen tree", "construction work", "road barrier", "traffic accident", "landslide"]
        detected = []

        for res in results:
            if isinstance(res, dict) and res.get('label') in block_labels and res.get('score', 0) > 0.4:
                 detected.append({
                     "label": res['label'],
                     "confidence": res['score'],
                     "box": []
                 })
        return detected
    except Exception as e:
        logger.error(f"HF Detection Error: {e}")
        return []
