"""
Background RTSP camera workers for automatic face-recognition attendance.

Each active camera runs in its own daemon thread. The worker connects to the
RTSP stream via OpenCV, captures frames at a configurable interval, runs
face_recognition against all registered employee encodings, and records
attendance automatically.
"""

import datetime
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

import cv2
import face_recognition
import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    AttendanceRecord,
    AttendanceStatus,
    Camera,
    CameraDirection,
    CheckMethod,
    Employee,
)

logger = logging.getLogger("rtsp_worker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(handler)

# ---------------------------------------------------------------------------
# Global registry of running workers
# ---------------------------------------------------------------------------

_workers: Dict[int, "CameraWorker"] = {}
_workers_lock = threading.Lock()

# Recent auto-detections kept in memory for the live endpoint
_recent_detections: List[dict] = []
_detections_lock = threading.Lock()

MAX_RECENT_DETECTIONS = 500  # ring-buffer cap


def _add_detection(detection: dict) -> None:
    with _detections_lock:
        _recent_detections.append(detection)
        # Trim old entries beyond cap
        if len(_recent_detections) > MAX_RECENT_DETECTIONS:
            del _recent_detections[: len(_recent_detections) - MAX_RECENT_DETECTIONS]


def get_recent_detections(minutes: int = 5) -> List[dict]:
    """Return detections from the last *minutes* minutes."""
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes)
    with _detections_lock:
        return [d for d in _recent_detections if d["detected_at"] >= cutoff]


# ---------------------------------------------------------------------------
# Face-encoding cache (shared across workers, refreshed periodically)
# ---------------------------------------------------------------------------

_encodings_cache: List[Tuple[int, str, str, Optional[str], np.ndarray]] = []
_encodings_lock = threading.Lock()
_encodings_last_loaded: float = 0.0


def _reload_encodings() -> None:
    """Load all active employee face encodings from the database."""
    global _encodings_last_loaded
    db: Session = SessionLocal()
    try:
        employees = (
            db.query(Employee)
            .filter(Employee.is_active.is_(True), Employee.face_encoding.isnot(None))
            .all()
        )
        new_cache = []
        for emp in employees:
            try:
                enc = np.array(json.loads(emp.face_encoding))
                new_cache.append(
                    (emp.id, emp.employee_id, emp.name, emp.department, enc)
                )
            except Exception:
                logger.warning("Skipping bad encoding for employee %s", emp.employee_id)
        with _encodings_lock:
            global _encodings_cache
            _encodings_cache = new_cache
        _encodings_last_loaded = time.monotonic()
        logger.info("Loaded %d employee face encodings", len(new_cache))
    except Exception:
        logger.exception("Failed to reload face encodings")
    finally:
        db.close()


def _get_encodings() -> List[Tuple[int, str, str, Optional[str], np.ndarray]]:
    """Return cached encodings, reloading if stale."""
    if time.monotonic() - _encodings_last_loaded > settings.RTSP_ENCODING_RELOAD_SECONDS:
        _reload_encodings()
    with _encodings_lock:
        return list(_encodings_cache)


# ---------------------------------------------------------------------------
# Camera worker
# ---------------------------------------------------------------------------


class CameraWorker:
    """Runs in a daemon thread, reading frames from one RTSP camera."""

    def __init__(self, camera_id: int, name: str, rtsp_url: str, direction: str, location: Optional[str] = None):
        self.camera_id = camera_id
        self.name = name
        self.rtsp_url = rtsp_url
        self.direction = direction
        self.location = location
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_frame_at: Optional[datetime.datetime] = None

        # Cooldown tracking: employee_id -> last detection time
        self._cooldowns: Dict[int, datetime.datetime] = {}

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"rtsp-cam-{self.camera_id}", daemon=True
        )
        self._thread.start()
        logger.info("Started worker for camera %d (%s)", self.camera_id, self.name)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("Stopped worker for camera %d (%s)", self.camera_id, self.name)

    # ---- internal -----------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            cap = None
            try:
                logger.info(
                    "Connecting to RTSP stream for camera %d (%s)…",
                    self.camera_id,
                    self.name,
                )
                cap = cv2.VideoCapture(self.rtsp_url)
                if not cap.isOpened():
                    logger.warning(
                        "Cannot open RTSP stream for camera %d. Retrying in %ds…",
                        self.camera_id,
                        settings.RTSP_RECONNECT_DELAY,
                    )
                    self._stop_event.wait(settings.RTSP_RECONNECT_DELAY)
                    continue

                logger.info("Connected to camera %d (%s)", self.camera_id, self.name)

                while not self._stop_event.is_set():
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning(
                            "Lost connection to camera %d. Reconnecting…",
                            self.camera_id,
                        )
                        break

                    self.last_frame_at = datetime.datetime.utcnow()
                    self._process_frame(frame)

                    # Wait for the configured interval (interruptible)
                    self._stop_event.wait(settings.RTSP_FRAME_INTERVAL)

            except Exception:
                logger.exception(
                    "Unexpected error in worker for camera %d", self.camera_id
                )
            finally:
                if cap is not None:
                    cap.release()

            # Delay before reconnect attempt
            if not self._stop_event.is_set():
                self._stop_event.wait(settings.RTSP_RECONNECT_DELAY)

    def _process_frame(self, frame: np.ndarray) -> None:
        """Detect faces in *frame* and match against known employees."""
        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect face locations & encodings
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        if not face_locations:
            return

        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        known = _get_encodings()
        if not known:
            return

        known_encs = [k[4] for k in known]

        for face_enc in face_encodings:
            distances = face_recognition.face_distance(known_encs, face_enc)
            best_idx = int(np.argmin(distances))
            best_distance = float(distances[best_idx])

            if best_distance > settings.FACE_RECOGNITION_TOLERANCE:
                logger.debug(
                    "Unrecognized face on camera %d (best distance=%.3f)",
                    self.camera_id,
                    best_distance,
                )
                continue

            emp_id, emp_code, emp_name, emp_dept, _ = known[best_idx]
            confidence = round(1.0 - best_distance, 4)

            # Cooldown check
            now = datetime.datetime.utcnow()
            last_seen = self._cooldowns.get(emp_id)
            if last_seen is not None:
                elapsed = (now - last_seen).total_seconds()
                if elapsed < settings.RTSP_COOLDOWN_MINUTES * 60:
                    continue

            self._cooldowns[emp_id] = now
            logger.info(
                "Recognized %s (employee=%s) on camera %d with confidence %.4f",
                emp_name,
                emp_code,
                self.camera_id,
                confidence,
            )

            self._record_attendance(emp_id, emp_code, emp_name, confidence, now)

            # Store for live feed
            _add_detection(
                {
                    "employee_name": emp_name,
                    "employee_id": emp_code,
                    "camera_name": self.name,
                    "camera_location": self.location,
                    "direction": self.direction,
                    "confidence": confidence,
                    "detected_at": now,
                }
            )

    def _record_attendance(
        self,
        emp_db_id: int,
        emp_code: str,
        emp_name: str,
        confidence: float,
        now: datetime.datetime,
    ) -> None:
        """Create or update an attendance record based on camera direction."""
        db: Session = SessionLocal()
        try:
            today = now.date()
            existing = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.employee_id == emp_db_id,
                    AttendanceRecord.date == today,
                )
                .first()
            )

            if self.direction == CameraDirection.entry.value:
                if existing:
                    logger.debug(
                        "%s already has attendance record for today (entry camera)",
                        emp_name,
                    )
                    return

                status_val = AttendanceStatus.present
                if now.hour >= 9:
                    status_val = AttendanceStatus.late

                record = AttendanceRecord(
                    employee_id=emp_db_id,
                    check_in=now,
                    date=today,
                    status=status_val,
                    method=CheckMethod.rtsp_auto,
                    confidence=confidence,
                )
                db.add(record)
                db.commit()
                logger.info("Auto check-in recorded for %s", emp_name)

            else:  # exit
                if not existing:
                    logger.debug(
                        "%s has no check-in today, ignoring exit detection",
                        emp_name,
                    )
                    return
                if existing.check_out is not None:
                    logger.debug(
                        "%s already checked out today", emp_name
                    )
                    return

                existing.check_out = now
                # Mark half-day if worked less than 4 hours
                if existing.check_in:
                    duration = (now - existing.check_in).total_seconds() / 3600
                    if duration < 4:
                        existing.status = AttendanceStatus.half_day

                db.commit()
                logger.info("Auto check-out recorded for %s", emp_name)

        except Exception:
            db.rollback()
            logger.exception("Failed to record attendance for %s", emp_name)
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Public helpers for managing workers
# ---------------------------------------------------------------------------


def start_camera_worker(camera: Camera) -> None:
    """Create and start a worker for the given camera."""
    with _workers_lock:
        if camera.id in _workers and _workers[camera.id].is_running:
            return
        worker = CameraWorker(
            camera_id=camera.id,
            name=camera.name,
            rtsp_url=camera.rtsp_url,
            direction=camera.direction.value if hasattr(camera.direction, "value") else camera.direction,
            location=camera.location,
        )
        _workers[camera.id] = worker
        worker.start()


def stop_camera_worker(camera_id: int) -> None:
    """Stop the worker for the given camera id."""
    with _workers_lock:
        worker = _workers.pop(camera_id, None)
    if worker:
        worker.stop()


def stop_all_workers() -> None:
    """Stop every running camera worker."""
    with _workers_lock:
        ids = list(_workers.keys())
    for cid in ids:
        stop_camera_worker(cid)


def start_all_active_cameras() -> None:
    """Start workers for every active camera in the database."""
    _reload_encodings()
    db: Session = SessionLocal()
    try:
        cameras = db.query(Camera).filter(Camera.is_active.is_(True)).all()
        for cam in cameras:
            start_camera_worker(cam)
        logger.info("Started workers for %d active cameras", len(cameras))
    finally:
        db.close()


def get_worker_status() -> Dict[int, dict]:
    """Return status information for all registered workers."""
    with _workers_lock:
        result = {}
        for cid, w in _workers.items():
            result[cid] = {
                "is_running": w.is_running,
                "last_frame_at": w.last_frame_at,
            }
        return result


def test_rtsp_connection(rtsp_url: str, timeout: int = 10) -> Tuple[bool, str]:
    """Try to open an RTSP stream and read one frame. Returns (success, message)."""
    cap = None
    try:
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            return False, "Could not open RTSP stream"
        ret, _ = cap.read()
        if not ret:
            return False, "Connected but could not read a frame"
        return True, "RTSP connection successful"
    except Exception as exc:
        return False, f"Error: {exc}"
    finally:
        if cap is not None:
            cap.release()
