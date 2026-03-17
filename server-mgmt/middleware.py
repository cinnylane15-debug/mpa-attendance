import time
import json
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database import log_audit


class AuditMiddleware(BaseHTTPMiddleware):
    """Log all mutating requests to the audit log."""

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.method in self.MUTATING_METHODS:
            # Extract user info if available
            user_id = None
            if hasattr(request.state, "user"):
                user_id = request.state.user.get("id")

            ip = request.client.host if request.client else "unknown"
            action = f"{request.method} {request.url.path}"

            try:
                await log_audit(
                    action=action,
                    user_id=user_id,
                    detail=json.dumps({"query": str(request.query_params)}),
                    ip_address=ip,
                    success=response.status_code < 400,
                )
            except Exception:
                pass  # Don't let audit logging break requests

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP."""

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60

        # Clean old entries and add current
        self.requests[ip] = [t for t in self.requests[ip] if t > window_start]
        self.requests[ip].append(now)

        if len(self.requests[ip]) > self.rpm:
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        return await call_next(request)
