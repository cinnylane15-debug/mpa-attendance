import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import get_current_user
from config import settings
from database import close_db, get_db, init_db
from middleware import AuditMiddleware, RateLimitMiddleware
from routers import (
    auth_router,
    commands,
    deploy,
    docker,
    files,
    network,
    packages,
    services,
    system,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    Path(settings.stacks_dir).mkdir(parents=True, exist_ok=True)
    print(f"Server Management API started on port {settings.api_port}")
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="MPA Server Management API",
    description="Remote server management API for the MPA Attendance System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins since we authenticate via JWT/API key
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit)

# Audit logging
app.add_middleware(AuditMiddleware)

# Mount routers
app.include_router(auth_router.router)
app.include_router(system.router)
app.include_router(packages.router)
app.include_router(docker.router)
app.include_router(deploy.router)
app.include_router(services.router)
app.include_router(files.router)
app.include_router(commands.router)
app.include_router(network.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "mpa-server-mgmt"}


@app.get("/audit/log", tags=["Audit"])
async def get_audit_log(
    limit: int = 50,
    action: str | None = None,
    user: dict = Depends(get_current_user),
):
    db = await get_db()
    if action:
        rows = await db.execute_fetchall(
            "SELECT id, timestamp, user_id, action, detail, ip_address, success FROM audit_log WHERE action LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{action}%", limit),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT id, timestamp, user_id, action, detail, ip_address, success FROM audit_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
    return [
        {
            "id": r[0],
            "timestamp": str(r[1]),
            "user_id": r[2],
            "action": r[3],
            "detail": r[4],
            "ip_address": r[5],
            "success": bool(r[6]),
        }
        for r in rows
    ]


if __name__ == "__main__":
    import uvicorn

    ssl_cert = settings.ssl_cert if Path(settings.ssl_cert).exists() else None
    ssl_key = settings.ssl_key if Path(settings.ssl_key).exists() else None

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.api_port,
        ssl_certfile=ssl_cert,
        ssl_keyfile=ssl_key,
        reload=False,
    )
