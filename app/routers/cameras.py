from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Camera, User, AttendanceRecord, UnknownFace, Student
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
            capture_mode=cam.capture_mode.value if cam.capture_mode else "snapshot",
            snapshot_url=cam.snapshot_url,
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


@router.post("/{camera_id}/test")
def test_camera_connection(
    camera_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Test camera connection (snapshot or RTSP)."""
    import cv2
    import httpx
    from app.rtsp_worker import derive_snapshot_url

    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    mode = cam.capture_mode.value if cam.capture_mode else "snapshot"

    if mode == "snapshot":
        snapshot_url = cam.snapshot_url or derive_snapshot_url(cam.rtsp_url)
        if not snapshot_url:
            return {"success": False, "message": "Could not derive snapshot URL"}
        try:
            from urllib.parse import urlparse
            parsed = urlparse(snapshot_url)
            username = parsed.username or ""
            password = parsed.password or ""
            clean_url = snapshot_url.replace(f"{username}:{password}@", "")
            with httpx.Client(timeout=10) as client:
                resp = client.get(clean_url, auth=httpx.DigestAuth(username, password))
                if resp.status_code == 200 and len(resp.content) > 1000:
                    return {"success": True, "message": f"Snapshot OK ({len(resp.content)} bytes)"}
                return {"success": False, "message": f"HTTP {resp.status_code}, {len(resp.content)} bytes"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    else:
        try:
            cap = cv2.VideoCapture(cam.rtsp_url)
            if not cap.isOpened():
                return {"success": False, "message": "Could not connect to RTSP stream"}
            ret, _ = cap.read()
            cap.release()
            if ret:
                return {"success": True, "message": "Connection successful, frame captured"}
            return {"success": False, "message": "Connected but could not read a frame"}
        except Exception as e:
            return {"success": False, "message": str(e)}


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

    mode = cam.capture_mode.value if cam.capture_mode else "snapshot"
    rtsp_manager.start_camera(cam.id, cam.name, cam.rtsp_url, cam.direction.value, mode, cam.snapshot_url)
    return {"message": f"Camera '{cam.name}' worker started ({mode} mode)"}


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


@router.get("/{camera_id}/logs")
def camera_logs(
    camera_id: int,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent activity for a camera: attendance records and unknown face captures."""
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Recent attendance from this camera
    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.camera_name == cam.name)
        .order_by(AttendanceRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    attendance_logs = []
    for r in records:
        student = r.student
        attendance_logs.append({
            "type": "attendance",
            "student_name": student.name if student else None,
            "student_code": student.student_id if student else None,
            "status": r.status.value,
            "confidence": r.confidence,
            "timestamp": r.check_in.isoformat() if r.check_in else r.created_at.isoformat(),
        })

    # Recent unknown faces from this camera
    unknowns = (
        db.query(UnknownFace)
        .filter(UnknownFace.camera_name == cam.name)
        .order_by(UnknownFace.captured_at.desc())
        .limit(limit)
        .all()
    )
    unknown_logs = []
    for u in unknowns:
        unknown_logs.append({
            "type": "unknown_face",
            "confidence": u.confidence,
            "is_resolved": u.is_resolved,
            "assigned_to": u.assigned_student.name if u.assigned_student else None,
            "timestamp": u.captured_at.isoformat() if u.captured_at else None,
        })

    # Merge and sort by timestamp
    all_logs = attendance_logs + unknown_logs
    all_logs.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    # Worker status
    running = rtsp_manager.is_running(camera_id)

    return {
        "camera_name": cam.name,
        "is_running": running,
        "capture_mode": cam.capture_mode.value if cam.capture_mode else "snapshot",
        "logs": all_logs[:limit],
    }
