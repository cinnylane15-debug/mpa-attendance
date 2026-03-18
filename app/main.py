import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.rtsp_worker import rtsp_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # ── Startup ───────────────────────────────────────────────────────────
    logger.info("Starting MPA Attendance System...")

    # Create database tables and enable pgvector
    create_tables()
    logger.info("Database tables created / verified")

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Initialize face engine (lazy - will load on first use)
    logger.info("Face engine will initialize on first use (model: %s)", settings.INSIGHTFACE_MODEL)

    # Start RTSP workers for active cameras
    try:
        rtsp_manager.start_active_cameras()
    except Exception as e:
        logger.error("Failed to start camera workers: %s", e)

    logger.info("MPA Attendance System started successfully")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("Shutting down MPA Attendance System...")
    rtsp_manager.stop_all()
    logger.info("All camera workers stopped")


app = FastAPI(
    title="MPA Attendance System",
    description="School attendance system using face recognition from Dahua IP cameras",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded photos as static files
if os.path.isdir(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# ── Register routers ─────────────────────────────────────────────────────────
from app.routers.auth_router import router as auth_router
from app.routers.students import router as students_router
from app.routers.classes import router as classes_router
from app.routers.attendance import router as attendance_router
from app.routers.cameras import router as cameras_router
from app.routers.schedules import router as schedules_router
from app.routers.holidays import router as holidays_router
from app.routers.dashboard import router as dashboard_router
from app.routers.unknown_faces import router as unknown_faces_router

app.include_router(auth_router)
app.include_router(students_router)
app.include_router(classes_router)
app.include_router(attendance_router)
app.include_router(cameras_router)
app.include_router(schedules_router)
app.include_router(holidays_router)
app.include_router(dashboard_router)
app.include_router(unknown_faces_router)


@app.get("/")
def root():
    return {"message": "MPA Attendance System API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
