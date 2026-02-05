from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import os
import httpx
import logging

from backend.database import Base, engine
from backend.ai_factory import create_all_ai_services
from backend.ai_interfaces import initialize_ai_services
from backend.bot import start_bot_thread, stop_bot_thread
from backend.init_db import migrate_db
from backend.maharashtra_locator import load_maharashtra_pincode_data, load_maharashtra_mla_data
from backend.exceptions import EXCEPTION_HANDLERS
from backend.routers import issues, detection, grievances, utility
from backend.grievance_service import GrievanceService
import backend.dependencies

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

if not is_production:
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

# Include Modular Routers
app.include_router(issues.router, tags=["Issues"])
app.include_router(detection.router, tags=["Detection"])
app.include_router(grievances.router, tags=["Grievances"])
app.include_router(utility.router, tags=["Utility"])

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "VishwaGuru API",
        "version": "1.0.0"
    }
