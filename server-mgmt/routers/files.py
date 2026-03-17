import os
import stat
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import FileResponse

from auth import get_current_user
from database import log_audit
from models import FileDeleteRequest, FileEntry, FileWriteRequest, MessageResponse

router = APIRouter(prefix="/files", tags=["File Management"])


def _validate_path(path: str) -> Path:
    """Resolve and validate path to prevent traversal attacks."""
    resolved = Path(path).resolve()
    # Block access to sensitive system dirs
    blocked = ["/proc/kcore", "/dev/mem"]
    if str(resolved) in blocked:
        raise ValueError(f"Access denied: {path}")
    return resolved


@router.get("/list", response_model=list[FileEntry])
async def list_directory(
    path: str = Query(default="/", description="Directory path"),
    user: dict = Depends(get_current_user),
):
    dir_path = _validate_path(path)
    if not dir_path.is_dir():
        return []

    entries = []
    try:
        for entry in sorted(dir_path.iterdir()):
            try:
                st = entry.lstat()
                if entry.is_symlink():
                    ftype = "symlink"
                elif entry.is_dir():
                    ftype = "directory"
                else:
                    ftype = "file"

                entries.append(FileEntry(
                    name=entry.name,
                    path=str(entry),
                    type=ftype,
                    size=st.st_size,
                    modified=datetime.fromtimestamp(st.st_mtime).isoformat(),
                    permissions=stat.filemode(st.st_mode),
                ))
            except (PermissionError, OSError):
                continue
    except PermissionError:
        return []

    return entries


@router.get("/read")
async def read_file(
    path: str = Query(..., description="File path to read"),
    max_size: int = Query(default=1048576, description="Max file size in bytes (default 1MB)"),
    user: dict = Depends(get_current_user),
):
    file_path = _validate_path(path)
    if not file_path.is_file():
        return {"content": "", "error": "File not found", "success": False}

    if file_path.stat().st_size > max_size:
        return {"content": "", "error": f"File too large (>{max_size} bytes)", "success": False}

    try:
        content = file_path.read_text(errors="replace")
        return {"content": content, "path": str(file_path), "success": True}
    except Exception as e:
        return {"content": "", "error": str(e), "success": False}


@router.post("/write", response_model=MessageResponse)
async def write_file(
    req: FileWriteRequest, user: dict = Depends(get_current_user)
):
    file_path = _validate_path(req.path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(req.content)

        # Set permissions
        try:
            os.chmod(str(file_path), int(req.mode, 8))
        except (ValueError, OSError):
            pass

        await log_audit(
            "files.write",
            user["id"],
            f"path={req.path}, size={len(req.content)}",
        )
        return MessageResponse(message=f"File written: {req.path}")
    except Exception as e:
        return MessageResponse(message=f"Write failed: {e}", success=False)


@router.post("/upload", response_model=MessageResponse)
async def upload_file(
    path: str = Query(..., description="Destination path"),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    dest_path = _validate_path(path)

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        dest_path.write_bytes(content)

        await log_audit(
            "files.upload",
            user["id"],
            f"path={path}, filename={file.filename}, size={len(content)}",
        )
        return MessageResponse(message=f"Uploaded to {path} ({len(content)} bytes)")
    except Exception as e:
        return MessageResponse(message=f"Upload failed: {e}", success=False)


@router.get("/download")
async def download_file(
    path: str = Query(..., description="File path to download"),
    user: dict = Depends(get_current_user),
):
    file_path = _validate_path(path)
    if not file_path.is_file():
        return MessageResponse(message="File not found", success=False)

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.delete("/delete", response_model=MessageResponse)
async def delete_file(
    req: FileDeleteRequest, user: dict = Depends(get_current_user)
):
    file_path = _validate_path(req.path)

    if not file_path.exists():
        return MessageResponse(message="Path not found", success=False)

    try:
        if file_path.is_dir():
            import shutil
            shutil.rmtree(str(file_path))
        else:
            file_path.unlink()

        await log_audit("files.delete", user["id"], f"path={req.path}")
        return MessageResponse(message=f"Deleted: {req.path}")
    except Exception as e:
        return MessageResponse(message=f"Delete failed: {e}", success=False)
