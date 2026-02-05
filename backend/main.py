from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import List, Optional, Any
from PIL import Image
from fastapi.concurrency import run_in_threadpool
import os
import sys
from pathlib import Path
import httpx
import logging
import time
import magic
import json
import shutil
import uuid
from backend.grievance_classifier import get_grievance_classifier
from backend.schemas import GrievanceRequest, ChatRequest, IssueResponse
from backend.exceptions import EXCEPTION_HANDLERS
from backend.database import Base, engine, get_db, SessionLocal
from backend.models import Issue
from backend.ai_factory import create_all_ai_services
from backend.ai_interfaces import initialize_ai_services, get_ai_services
from backend.ai_service import chat_with_civic_assistant, generate_action_plan
from backend.bot import run_bot
from backend.init_db import migrate_db
from backend.maharashtra_locator import load_maharashtra_pincode_data, load_maharashtra_mla_data, find_constituency_by_pincode, find_mla_by_constituency
from backend.cache import recent_issues_cache
from backend.pothole_detection import detect_potholes
from backend.garbage_detection import detect_garbage
from backend.local_ml_service import detect_infrastructure_local, detect_flooding_local, detect_vandalism_local
from backend.unified_detection_service import get_detection_status
from backend.hf_api_service import (
    detect_illegal_parking_clip,
    detect_street_light_clip,
    detect_fire_clip,
    detect_stray_animal_clip,
    detect_blocked_road_clip,
    detect_tree_hazard_clip,
    detect_pest_clip,
    detect_severity_clip,
    detect_smart_scan_clip,
    generate_image_caption
)

def validate_image_for_processing(image):
    if not image:
        pass

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Migrate DB
    migrate_db()

    # Startup: Initialize Shared HTTP Client for external APIs (Connection Pooling)
    app.state.http_client = httpx.AsyncClient()
    # Set global shared client in dependencies for cached functions
    backend.dependencies.SHARED_HTTP_CLIENT = app.state.http_client
    logger.info("Shared HTTP Client initialized.")

    # Startup: Initialize AI services
    try:
        action_plan_service, chat_service, mla_summary_service = create_all_ai_services()

        initialize_ai_services(
            action_plan_service=action_plan_service,
            chat_service=chat_service,
            mla_summary_service=mla_summary_service
        )
        logger.info("AI services initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing AI services: {e}", exc_info=True)
        # We don't raise here to allow partial startup if AI fails?
        # Original code raised. Let's raise.
        raise

    # Startup: Initialize Grievance Service
    try:
        grievance_service = GrievanceService()
        app.state.grievance_service = grievance_service
        logger.info("Grievance service initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing grievance service: {e}", exc_info=True)
        raise

    # Startup: Load static data to avoid first-request latency
    try:
        # These functions use lru_cache, so calling them once loads the data into memory
        load_maharashtra_pincode_data()
        load_maharashtra_mla_data()
        logger.info("Maharashtra data pre-loaded successfully.")
    except Exception as e:
        logger.error(f"Error pre-loading Maharashtra data: {e}")

    # Startup: Start Telegram Bot in separate thread (non-blocking for FastAPI)
    try:
        start_bot_thread()
        logger.info("Telegram bot started in separate thread.")
    except Exception as e:
        logger.error(f"Error starting bot thread: {e}")
    
    yield
    
    # Shutdown: Close Shared HTTP Client
    if app.state.http_client:
        await app.state.http_client.aclose()
    logger.info("Shared HTTP Client closed.")

    # Shutdown: Stop Telegram Bot thread
    try:
        stop_bot_thread()
        logger.info("Telegram bot thread stopped.")
    except Exception as e:
        logger.error(f"Error stopping bot thread: {e}")

app = FastAPI(
    title="VishwaGuru Backend",
    description="AI-powered civic issue reporting and resolution platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add centralized exception handlers
for exception_type, handler in EXCEPTION_HANDLERS.items():
    app.add_exception_handler(exception_type, handler)

# CORS Configuration - Security Enhanced
frontend_url = os.environ.get("FRONTEND_URL")
is_production = os.environ.get("ENVIRONMENT", "").lower() == "production"

if not frontend_url:
    if is_production:
        raise ValueError(
            "FRONTEND_URL environment variable is required for security in production. "
            "Set it to your frontend URL (e.g., https://your-app.netlify.app)."
        )
    else:
        logger.warning("FRONTEND_URL not set. Defaulting to http://localhost:5173 for development.")
        frontend_url = "http://localhost:5173"

if not (frontend_url.startswith("http://") or frontend_url.startswith("https://")):
    raise ValueError(
        f"FRONTEND_URL must be a valid HTTP/HTTPS URL. Got: {frontend_url}"
    )

allowed_origins = [frontend_url]

if os.environ.get("ENVIRONMENT", "").lower() != "production":
    dev_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
    ]
    allowed_origins.extend(dev_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=500)

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "VishwaGuru API",
        "version": "1.0.0"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/ml-status")
async def ml_status():
    """
    Get the status of the ML detection service.
    Returns information about which backend is being used (local or HF API).
    """
    status = await get_detection_status()
    return {
        "status": "ok",
        "ml_service": status
    }

def save_file_blocking(file_obj, path):
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file_obj, buffer)

def save_issue_db(db: Session, issue: Issue):
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue

@app.post("/api/issues")
async def create_issue(
    background_tasks: BackgroundTasks,
    description: str = Form(...),
    category: str = Form(...),
    user_email: str = Form(None),
    latitude: float = Form(None),
    longitude: float = Form(None),
    location: str = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    image_path = None
    
    try:
        # Validate uploaded image if provided
        if image:
            validate_uploaded_file(image)
        
        # Save image if provided
        if image:
            upload_dir = "data/uploads"
            os.makedirs(upload_dir, exist_ok=True)
            filename = f"{uuid.uuid4()}_{image.filename}"
            image_path = os.path.join(upload_dir, filename)
            await run_in_threadpool(save_file_blocking, image.file, image_path)
    except HTTPException:
        # Re-raise HTTP exceptions (from validation)
        raise
    except OSError as e:
        logger.error(f"File I/O error while saving image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    except Exception as e:
        logger.error(f"Unexpected error during file processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    try:
        # Save to DB
        new_issue = Issue(
            description=description,
            category=category,
            image_path=image_path,
            source="web",
            user_email=user_email,
            latitude=latitude,
            longitude=longitude,
            location=location,
            action_plan=None
        )

        # Offload blocking DB operations to threadpool
        await run_in_threadpool(save_issue_db, db, new_issue)
    except Exception as e:
        # Clean up uploaded file if DB save failed
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError:
                pass  # Ignore cleanup errors
        
        logger.error(f"Database error while creating issue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save issue to database")

    # Add background task for AI generation
    background_tasks.add_task(process_action_plan_background, new_issue.id, description, category, image_path)

    return {
        "id": new_issue.id,
        "message": "Issue reported successfully. Action plan generating in background.",
        "action_plan": None
    }

@app.post("/api/issues/{issue_id}/vote")
def upvote_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Increment upvotes
    if issue.upvotes is None:
        issue.upvotes = 0
    issue.upvotes += 1

    db.commit()
    db.refresh(issue)

    return {"id": issue.id, "upvotes": issue.upvotes, "message": "Upvoted successfully"}

@lru_cache(maxsize=1)
def _load_responsibility_map():
    # Assuming the data folder is at the root level relative to where backend is run
    # Adjust path as necessary. If running from root, it is "data/responsibility_map.json"
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "responsibility_map.json")

    with open(file_path, "r") as f:
        return json.load(f)

@app.get("/api/responsibility-map")
def get_responsibility_map():
    # In a real app, this might read from the file or database
    # For MVP, we can return the structure directly or read the file
    try:
        return _load_responsibility_map()
    except FileNotFoundError:
        logger.error("Responsibility map file not found", exc_info=True)
        raise HTTPException(status_code=404, detail="Data file not found")
    except Exception as e:
        logger.error(f"Error loading responsibility map: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        response = await chat_with_civic_assistant(request.query)
        return {"response": response}
    except Exception as e:
        logger.error(f"Chat service error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Chat service temporarily unavailable")

@app.get("/api/issues/recent", response_model=List[IssueResponse])
def get_recent_issues(db: Session = Depends(get_db)):
    cached_data = recent_issues_cache.get()
    if cached_data:
        return JSONResponse(content=cached_data)

    # Optimized query: Fetch only needed columns and truncate description in DB
    # We explicitly exclude action_plan to save bandwidth/IO
    query = db.query(
        Issue.id,
        Issue.category,
        Issue.created_at,
        Issue.image_path,
        Issue.status,
        Issue.upvotes,
        Issue.location,
        Issue.latitude,
        Issue.longitude,
        # Truncate description in SQL.
        func.substr(Issue.description, 1, 100).label("description_snippet"),
        func.length(Issue.description).label("description_len")
    ).order_by(Issue.created_at.desc()).limit(10)

    results = query.all()

    data = []
    for row in results:
        desc = row.description_snippet or ""
        # If description was truncated (length > 100), append "..."
        if (row.description_len or 0) > 100:
             desc += "..."

        data.append(IssueResponse(
            id=row.id,
            category=row.category,
            description=desc,
            created_at=row.created_at,
            image_path=row.image_path,
            status=row.status,
            upvotes=row.upvotes if row.upvotes is not None else 0,
            location=row.location,
            latitude=row.latitude,
            longitude=row.longitude,
            action_plan=None # Explicitly None as we didn't fetch it
        ).model_dump(mode='json'))

    recent_issues_cache.set(data)

    return data

@app.post("/api/detect-pothole")
async def detect_pothole_endpoint(image: UploadFile = File(...)):
    # Validate uploaded file
    validate_uploaded_file(image)
    
    # Convert to PIL Image directly from file object to save memory
    try:
        pil_image = await run_in_threadpool(Image.open, image.file)
        # Validate image for processing
        validate_image_for_processing(pil_image)
    except HTTPException:
        raise  # Re-raise HTTP exceptions from validation
    except Exception as e:
        logger.error(f"Invalid image file for pothole detection: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Run detection (blocking, so run in threadpool)
    try:
        detections = await run_in_threadpool(detect_potholes, pil_image)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Pothole detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Detection service temporarily unavailable")

@app.post("/api/detect-infrastructure")
async def detect_infrastructure_endpoint(image: UploadFile = File(...)):
    # Validate uploaded file
    validate_uploaded_file(image)
    
    # Convert to PIL Image directly from file object to save memory
    try:
        pil_image = await run_in_threadpool(Image.open, image.file)
        # Validate image for processing
        validate_image_for_processing(pil_image)
    except HTTPException:
        raise  # Re-raise HTTP exceptions from validation
    except Exception as e:
        logger.error(f"Invalid image file for infrastructure detection: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Run detection using unified service (local ML by default)
    try:
        # Use shared HTTP client from app state
        client = request.app.state.http_client
        detections = await detect_infrastructure_local(pil_image, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Infrastructure detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Detection service temporarily unavailable")

@app.post("/api/detect-flooding")
async def detect_flooding_endpoint(image: UploadFile = File(...)):
    # Validate uploaded file
    validate_uploaded_file(image)
    
    # Convert to PIL Image directly from file object to save memory
    try:
        pil_image = await run_in_threadpool(Image.open, image.file)
        # Validate image for processing
        validate_image_for_processing(pil_image)
    except HTTPException:
        raise  # Re-raise HTTP exceptions from validation
    except Exception as e:
        logger.error(f"Invalid image file for flooding detection: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Run detection using unified service (local ML by default)
    try:
        # Use shared HTTP client from app state
        client = request.app.state.http_client
        detections = await detect_flooding_local(pil_image, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Flooding detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Detection service temporarily unavailable")

@app.post("/api/detect-vandalism")
async def detect_vandalism_endpoint(image: UploadFile = File(...)):
    # Validate uploaded file
    validate_uploaded_file(image)
    
    # Convert to PIL Image directly from file object to save memory
    try:
        pil_image = await run_in_threadpool(Image.open, image.file)
        # Validate image for processing
        validate_image_for_processing(pil_image)
    except HTTPException:
        raise  # Re-raise HTTP exceptions from validation
    except Exception as e:
        logger.error(f"Invalid image file for vandalism detection: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Run detection using unified service (local ML by default)
    try:
        # Use shared HTTP client from app state
        client = request.app.state.http_client
        detections = await detect_vandalism_local(pil_image, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Vandalism detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Detection service temporarily unavailable")

@app.post("/api/detect-garbage")
async def detect_garbage_endpoint(image: UploadFile = File(...)):
    # Validate uploaded file
    validate_uploaded_file(image)
    
    # Convert to PIL Image directly from file object to save memory
    try:
        pil_image = await run_in_threadpool(Image.open, image.file)
        # Validate image for processing
        validate_image_for_processing(pil_image)
    except HTTPException:
        raise  # Re-raise HTTP exceptions from validation
    except Exception as e:
        logger.error(f"Invalid image file for garbage detection: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Run detection (blocking, so run in threadpool)
    try:
        detections = await run_in_threadpool(detect_garbage, pil_image)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Garbage detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Detection service temporarily unavailable")

@app.post("/api/detect-illegal-parking")
async def detect_illegal_parking_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        detections = await detect_illegal_parking_clip(image_bytes, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Illegal parking detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/detect-street-light")
async def detect_street_light_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        detections = await detect_street_light_clip(image_bytes, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Street light detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/detect-fire")
async def detect_fire_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        detections = await detect_fire_clip(image_bytes, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Fire detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/detect-stray-animal")
async def detect_stray_animal_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        detections = await detect_stray_animal_clip(image_bytes, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Stray animal detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/detect-blocked-road")
async def detect_blocked_road_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        detections = await detect_blocked_road_clip(image_bytes, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Blocked road detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/detect-tree-hazard")
async def detect_tree_hazard_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        detections = await detect_tree_hazard_clip(image_bytes, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Tree hazard detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/detect-pest")
async def detect_pest_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        detections = await detect_pest_clip(image_bytes, client=client)
        return {"detections": detections}
    except Exception as e:
        logger.error(f"Pest detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/detect-severity")
async def detect_severity_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        result = await detect_severity_clip(image_bytes, client=client)
        return result
    except Exception as e:
        logger.error(f"Severity detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/detect-smart-scan")
async def detect_smart_scan_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        result = await detect_smart_scan_clip(image_bytes, client=client)
        return result
    except Exception as e:
        logger.error(f"Smart scan detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/generate-description")
async def generate_description_endpoint(request: Request, image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
    except Exception as e:
        logger.error(f"Invalid image file: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        client = request.app.state.http_client
        description = await generate_image_caption(image_bytes, client=client)
        if not description:
            return {"description": "", "error": "Could not generate description"}
        return {"description": description}
    except Exception as e:
        logger.error(f"Description generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/mh/rep-contacts")
async def get_maharashtra_rep_contacts(pincode: str = Query(..., min_length=6, max_length=6)):
    """
    Get MLA and representative contact information for Maharashtra by pincode.
    
    Args:
        pincode: 6-digit pincode for Maharashtra
        
    Returns:
        JSON with MLA details, constituency info, and grievance portal links
    """
    # Validate pincode format
    if not pincode.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Invalid pincode format. Must be 6 digits."
        )
    
    # Find constituency by pincode
    constituency_info = find_constituency_by_pincode(pincode)
    
    if not constituency_info:
        raise HTTPException(
            status_code=404,
            detail="Unknown pincode for Maharashtra MVP. Currently only supporting limited pincodes."
        )
    
    # Find MLA by constituency
    # If constituency_info exists but assembly_constituency is None, it means we only found District info via fallback
    assembly_constituency = constituency_info.get("assembly_constituency")
    mla_info = None

    if assembly_constituency:
        mla_info = find_mla_by_constituency(assembly_constituency)
    
    # If explicit MLA lookup failed or wasn't possible, create a generic placeholder
    if not mla_info:
        mla_info = {
            "mla_name": "MLA Info Unavailable",
            "party": "N/A",
            "phone": "N/A",
            "email": "N/A",
            "twitter": "Not Available"
        }
        # If we have a district but no constituency, explain it
        if not assembly_constituency:
             constituency_info["assembly_constituency"] = "Unknown (District Found)"
    
    # Generate AI summary (optional)
    description = None
    try:
        # Only generate summary if we have a valid constituency and MLA
        if assembly_constituency and mla_info["mla_name"] != "MLA Info Unavailable":
            ai_services = get_ai_services()
            description = await ai_services.mla_summary_service.generate_mla_summary(
                district=constituency_info["district"],
                assembly_constituency=assembly_constituency,
                mla_name=mla_info["mla_name"]
            )
    except Exception as e:
        logger.error(f"Error generating MLA summary: {e}")
        # Continue without description
    
    # Build response
    response = {
        "pincode": pincode,
        "state": constituency_info["state"],
        "district": constituency_info["district"],
        "assembly_constituency": constituency_info["assembly_constituency"],
        "mla": {
            "name": mla_info["mla_name"],
            "party": mla_info["party"],
            "phone": mla_info["phone"],
            "email": mla_info["email"],
            "twitter": mla_info.get("twitter")
        },
        "grievance_links": {
            "central_cpgrams": "https://pgportal.gov.in/",
            "maharashtra_portal": "https://aaplesarkar.mahaonline.gov.in/en",
            "note": "This is an MVP; data may not be fully accurate."
        }
    }
    
    # Add description if generated
    if description:
        response["description"] = description
    elif mla_info["mla_name"] == "MLA Info Unavailable":
        response["description"] = f"We found that {pincode} belongs to {constituency_info['district']} district, but we don't have the specific MLA details for this exact pincode yet."

    return response

# Note: Frontend serving code removed for separate deployment
# The frontend will be deployed on Netlify and make API calls to this backend

@app.post("/api/classify-grievance")
def classify_grievance_endpoint(request: GrievanceRequest):
    classifier = get_grievance_classifier()
    category = classifier.predict(request.text)
    return {"category": category}
