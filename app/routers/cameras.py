from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Camera, User
from app.rtsp_worker import rtsp_manager
from app.schemas import CameraCreate, CameraUpdate, CameraResponse

router = APIRouter(prefix="/api/cameras", tags=["Cameras"])


@router.post("/", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def create_camera(
    cam_in: CameraCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new camera (admin only)."""
    camera = Camera(
        name=cam_in.name,
        location=cam_in.location,
        rtsp_url=cam_in.rtsp_url,
        is_active=cam_in.is_active,
        direction=cam_in.direction,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/", response_model=list[CameraResponse])
def list_cameras(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all cameras."""
    cameras = db.query(Camera).order_by(Camera.name).all()
    results = []
    for cam in cameras:
        resp = CameraResponse(
            id=cam.id,
            name=cam.name,
            location=cam.location,
            rtsp_url=cam.rtsp_url,
            is_active=cam.is_active,
            direction=cam.direction.value,
            created_at=cam.created_at,
        )
        results.append(resp)
    return results


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single camera."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraResponse(
        id=cam.id,
        name=cam.name,
        location=cam.location,
        rtsp_url=cam.rtsp_url,
        is_active=cam.is_active,
        direction=cam.direction.value,
        created_at=cam.created_at,
    )


@router.put("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: int,
    cam_in: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a camera (admin only)."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    for key, value in cam_in.model_dump(exclude_unset=True).items():
        setattr(cam, key, value)
    db.commit()
    db.refresh(cam)
    return CameraResponse(
        id=cam.id,
        name=cam.name,
        location=cam.location,
        rtsp_url=cam.rtsp_url,
        is_active=cam.is_active,
        direction=cam.direction.value,
        created_at=cam.created_at,
    )


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a camera (admin only)."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    # Stop worker if running
    rtsp_manager.stop_camera(camera_id)
    db.delete(cam)
    db.commit()


@router.post("/{camera_id}/start")
def start_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Start the RTSP worker for a camera."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    rtsp_manager.start_camera(cam.id, cam.name, cam.rtsp_url, cam.direction.value)
    return {"message": f"Camera '{cam.name}' worker started"}


@router.post("/{camera_id}/stop")
def stop_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Stop the RTSP worker for a camera."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    rtsp_manager.stop_camera(cam.id)
    return {"message": f"Camera '{cam.name}' worker stopped"}


@router.get("/{camera_id}/status")
def camera_status(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a camera worker is running."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    running = rtsp_manager.is_running(camera_id)
    return {"camera_id": camera_id, "name": cam.name, "is_running": running}
