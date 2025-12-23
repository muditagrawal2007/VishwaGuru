from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, Issue
from ai_service import generate_action_plan
import json
import os
import shutil
from functools import lru_cache
import uuid
import asyncio
from fastapi import Depends
from contextlib import asynccontextmanager
from bot import run_bot

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Telegram Bot
    bot_app = await run_bot()
    yield
    # Shutdown: Stop Telegram Bot
    if bot_app:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

app = FastAPI(title="VishwaGuru Backend", lifespan=lifespan)

# CORS Configuration
# For separate frontend/backend deployment (e.g., Netlify + Render)
# Set FRONTEND_URL environment variable to your Netlify URL
# Example: https://your-app.netlify.app
frontend_url = os.environ.get("FRONTEND_URL", "*")
allowed_origins = [frontend_url] if frontend_url != "*" else ["*"]

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    description: str = Form(...),
    category: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    # Save image if provided
    image_path = None
    if image:
        upload_dir = "data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        # Generate unique filename
        filename = f"{uuid.uuid4()}_{image.filename}"
        image_path = os.path.join(upload_dir, filename)

        # Offload blocking file I/O to threadpool
        await run_in_threadpool(save_file_blocking, image.file, image_path)

    # Save to DB
    new_issue = Issue(
        description=description,
        category=category,
        image_path=image_path,
        source="web"
    )

    # Offload blocking DB operations to threadpool
    await run_in_threadpool(save_issue_db, db, new_issue)

    # Generate Action Plan (AI)
    action_plan = await generate_action_plan(description, category, image_path)

    return {
        "id": new_issue.id,
        "message": "Issue reported successfully",
        "action_plan": action_plan
    }

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
        return {"error": "Data file not found"}

# Note: Frontend serving code removed for separate deployment
# The frontend will be deployed on Netlify and make API calls to this backend
