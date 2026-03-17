import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Camera
from app.rtsp_worker import (
    get_worker_status,
    start_camera_worker,
    stop_camera_worker,
    test_rtsp_connection,
)
from app.schemas import CameraCreate, CameraResponse, CameraStatusResponse, CameraUpdate

router = APIRouter(prefix="/api/cameras", tags=["Cameras"])


@router.get("/", response_model=List[CameraResponse])
def list_cameras(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List all cameras."""
    cameras = db.query(Camera).order_by(Camera.created_at.desc()).all()
    return cameras


@router.post("/", response_model=CameraResponse, status_code=201)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Add a new camera."""
    camera = Camera(
        name=payload.name,
        location=payload.location,
        rtsp_url=payload.rtsp_url,
        direction=payload.direction,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)

    # Auto-start worker for the new camera
    if camera.is_active:
        start_camera_worker(camera)

    return camera


@router.get("/status", response_model=List[CameraStatusResponse])
def cameras_status(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Show which cameras are actively processing."""
    cameras = db.query(Camera).order_by(Camera.id).all()
    worker_status = get_worker_status()
    result = []
    for cam in cameras:
        ws = worker_status.get(cam.id, {})
        result.append(
            CameraStatusResponse(
                id=cam.id,
                name=cam.name,
                location=cam.location,
                direction=cam.direction,
                is_active=cam.is_active,
                is_processing=ws.get("is_running", False),
                last_frame_at=ws.get("last_frame_at"),
            )
        )
    return result


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get details of a single camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.put("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Update a camera's configuration."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(camera, key, value)

    db.commit()
    db.refresh(camera)

    # Restart worker if the camera config changed
    stop_camera_worker(camera.id)
    if camera.is_active:
        start_camera_worker(camera)

    return camera


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Delete a camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    stop_camera_worker(camera.id)
    db.delete(camera)
    db.commit()
    return {"detail": "Camera deleted"}


@router.post("/{camera_id}/test")
def test_camera_connection(
    camera_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Test the RTSP connection for a camera."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    success, message = test_rtsp_connection(camera.rtsp_url)
    return {"success": success, "message": message, "camera_name": camera.name}
