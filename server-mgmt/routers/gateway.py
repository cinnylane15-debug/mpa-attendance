"""GET-based gateway for environments where POST requests are blocked by proxies."""

import urllib.parse
from fastapi import APIRouter, HTTPException, Query
from auth import (
    create_access_token,
    create_refresh_token,
    verify_password,
    decode_token,
)
from database import get_db, log_audit
from utils.shell import run_command

router = APIRouter(prefix="/gw", tags=["Gateway"])


@router.get("/login")
async def gw_login(
    username: str = Query(...),
    password: str = Query(...),
):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    )
    if not rows or not verify_password(password, rows[0][2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, uname = rows[0][0], rows[0][1]
    return {
        "access_token": create_access_token(user_id, uname),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }


@router.get("/exec")
async def gw_exec(
    token: str = Query(...),
    cmd: str = Query(...),
    timeout: int = Query(default=120, ge=1, le=600),
    cwd: str | None = Query(default=None),
):
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    db = await get_db()
    user_id = int(payload["sub"])
    row = await db.execute_fetchall(
        "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
    )
    if not row:
        raise HTTPException(status_code=401, detail="User not found")

    command = urllib.parse.unquote(cmd)
    result = await run_command(command=command, timeout=timeout, cwd=cwd)

    await log_audit(
        "gw.exec",
        user_id,
        f"cmd={command[:200]}, rc={result.returncode}",
        success=result.success,
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.success,
    }


@router.get("/file/read")
async def gw_read_file(
    token: str = Query(...),
    path: str = Query(...),
):
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    from pathlib import Path

    p = Path(path).resolve()
    if not p.is_file():
        return {"content": "", "error": "Not found", "success": False}
    if p.stat().st_size > 1048576:
        return {"content": "", "error": "Too large (>1MB)", "success": False}
    return {"content": p.read_text(errors="replace"), "success": True}


@router.get("/file/write")
async def gw_write_file(
    token: str = Query(...),
    path: str = Query(...),
    content: str = Query(...),
):
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    from pathlib import Path

    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(urllib.parse.unquote(content))

    user_id = int(payload["sub"])
    await log_audit("gw.file.write", user_id, f"path={path}")

    return {"message": f"Written: {path}", "success": True}
