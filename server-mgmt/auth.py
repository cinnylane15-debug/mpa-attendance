import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
import bcrypt as _bcrypt
from jose import JWTError, jwt

from config import settings
from database import get_db

security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def generate_api_key() -> str:
    """Generate a random API key with mgmt_ prefix."""
    return f"mgmt_{secrets.token_hex(32)}"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    api_key: str | None = Depends(api_key_header),
) -> dict:
    """Authenticate via JWT bearer token or API key."""
    db = await get_db()

    # Try JWT first
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload["sub"])
        row = await db.execute_fetchall(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        )
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        return {"id": row[0][0], "username": row[0][1], "role": row[0][2]}

    # Try API key
    if api_key:
        prefix = api_key[:12]
        rows = await db.execute_fetchall(
            "SELECT id, key_hash, created_by FROM api_keys WHERE key_prefix = ?",
            (prefix,),
        )
        for row in rows:
            if verify_password(api_key, row[1]):
                # Update last_used_at
                await db.execute(
                    "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row[0],),
                )
                await db.commit()
                # Get the user who created this key
                user_rows = await db.execute_fetchall(
                    "SELECT id, username, role FROM users WHERE id = ?",
                    (row[2],),
                )
                if user_rows:
                    return {
                        "id": user_rows[0][0],
                        "username": user_rows[0][1],
                        "role": user_rows[0][2],
                    }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )
