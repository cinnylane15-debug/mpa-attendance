import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import auth_router, employees, attendance, dashboard

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
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

# Include routers
app.include_router(auth_router.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(dashboard.router)

# Redis client stored on app state
redis_client = None


@app.on_event("startup")
def startup_event():
    global redis_client
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        db=settings.REDIS_DB,
        decode_responses=True,
    )
    try:
        redis_client.ping()
        print("Connected to Redis")
    except redis.ConnectionError:
        print("Warning: Could not connect to Redis. Caching disabled.")
        redis_client = None
    app.state.redis = redis_client


@app.on_event("shutdown")
def shutdown_event():
    if app.state.redis:
        app.state.redis.close()
        print("Redis connection closed")


@app.get("/", tags=["Root"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    redis_ok = False
    if app.state.redis:
        try:
            app.state.redis.ping()
            redis_ok = True
        except Exception:
            pass

    db_ok = False
    try:
        from app.database import SessionLocal
        session = SessionLocal()
        session.execute("SELECT 1")
        session.close()
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if (db_ok and redis_ok) else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
    }
