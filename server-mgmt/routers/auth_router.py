from fastapi import APIRouter, Depends, HTTPException, status

from auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    get_current_user,
    hash_password,
    verify_password,
)
from database import get_db
from models import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListItem,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (req.username,),
    )
    if not rows or not verify_password(req.password, rows[0][2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, username = rows[0][0], rows[0][1]
    return TokenResponse(
        access_token=create_access_token(user_id, username),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest):
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = int(payload["sub"])
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, username FROM users WHERE id = ?", (user_id,)
    )
    if not rows:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(rows[0][0], rows[0][1]),
        refresh_token=create_refresh_token(rows[0][0]),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, username, role, created_at FROM users WHERE id = ?",
        (user["id"],),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=rows[0][0],
        username=rows[0][1],
        role=rows[0][2],
        created_at=str(rows[0][3]),
    )


@router.post("/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    req: ApiKeyCreateRequest, user: dict = Depends(get_current_user)
):
    raw_key = generate_api_key()
    key_hash = hash_password(raw_key)
    key_prefix = raw_key[:12]

    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO api_keys (name, key_hash, key_prefix, created_by) VALUES (?, ?, ?, ?)",
        (req.name, key_hash, key_prefix, user["id"]),
    )
    await db.commit()

    return ApiKeyCreateResponse(
        id=cursor.lastrowid,
        name=req.name,
        key=raw_key,
        key_prefix=key_prefix,
        created_at="now",
    )


@router.get("/api-keys", response_model=list[ApiKeyListItem])
async def list_api_keys(user: dict = Depends(get_current_user)):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, name, key_prefix, created_at, last_used_at FROM api_keys WHERE created_by = ?",
        (user["id"],),
    )
    return [
        ApiKeyListItem(
            id=row[0],
            name=row[1],
            key_prefix=row[2],
            created_at=str(row[3]),
            last_used_at=str(row[4]) if row[4] else None,
        )
        for row in rows
    ]


@router.delete("/api-keys/{key_id}", response_model=MessageResponse)
async def delete_api_key(key_id: int, user: dict = Depends(get_current_user)):
    db = await get_db()
    result = await db.execute(
        "DELETE FROM api_keys WHERE id = ? AND created_by = ?",
        (key_id, user["id"]),
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return MessageResponse(message="API key revoked")
