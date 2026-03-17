import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import auth_router, employees, attendance, dashboard

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(dashboard.router)

# Redis client stored on app state
redis_client = None


@app.on_event("startup")
def on_startup():
    global redis_client
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Connect to Redis
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )
    app.state.redis = redis_client
    try:
        redis_client.ping()
        print("Redis connected successfully")
    except redis.ConnectionError:
        print("Warning: Redis connection failed. Continuing without cache.")


@app.on_event("shutdown")
def on_shutdown():
    global redis_client
    if redis_client:
        redis_client.close()


@app.get("/", tags=["Health"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
def health_check():
    db_status = "unknown"
    redis_status = "unknown"

    # Check database
    try:
        from sqlalchemy import text
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Check Redis
    try:
        if redis_client and redis_client.ping():
            redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return {"status": "healthy", "database": db_status, "redis": redis_status}
