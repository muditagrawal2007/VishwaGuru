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
