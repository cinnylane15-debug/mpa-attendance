import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone, date

import cv2
import numpy as np
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.face_engine import face_engine
from app.models import AttendanceRecord, AttendanceStatus, AttendanceMethod, Camera, Student

logger = logging.getLogger(__name__)


class RecentDetection:
    """A recent face detection for the live feed."""

    def __init__(self, student_name: str, student_id: str, camera_name: str,
                 confidence: float, timestamp: datetime):
        self.student_name = student_name
        self.student_id = student_id
        self.camera_name = camera_name
        self.confidence = confidence
        self.timestamp = timestamp

    def to_dict(self) -> dict:
        return {
            "student_name": self.student_name,
            "student_id": self.student_id,
            "camera_name": self.camera_name,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat(),
        }


class CameraWorker:
    """Background worker that processes RTSP stream from a single camera."""

    def __init__(self, camera_id: int, camera_name: str, rtsp_url: str, direction: str):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.direction = direction
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        # Cooldown: track last attendance time per student to prevent duplicates
        self._last_attendance: dict[int, datetime] = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("Worker for camera %s is already running", self.camera_name)
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"cam-{self.camera_name}")
        self._thread.start()
        logger.info("Started RTSP worker for camera: %s", self.camera_name)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
            logger.info("Stopped RTSP worker for camera: %s", self.camera_name)

    def _is_on_cooldown(self, student_db_id: int) -> bool:
        last = self._last_attendance.get(student_db_id)
        if last is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return elapsed < settings.RTSP_COOLDOWN_MINUTES

    def _run(self):
        while not self._stop_event.is_set():
            cap = None
            try:
                logger.info("Connecting to RTSP stream: %s", self.rtsp_url)
                cap = cv2.VideoCapture(self.rtsp_url)
                if not cap.isOpened():
                    logger.error("Failed to open RTSP stream: %s", self.rtsp_url)
                    self._stop_event.wait(settings.RTSP_RECONNECT_DELAY)
                    continue

                logger.info("Connected to RTSP stream: %s", self.camera_name)

                while not self._stop_event.is_set():
                    ret, frame = cap.read()
                    if not ret:
                        logger.warning("Lost connection to camera: %s", self.camera_name)
                        break

                    self._process_frame(frame)
                    self._stop_event.wait(settings.RTSP_FRAME_INTERVAL)

            except Exception as e:
                logger.error("Error in RTSP worker for %s: %s", self.camera_name, e)
            finally:
                if cap is not None:
                    cap.release()

            if not self._stop_event.is_set():
                logger.info("Reconnecting to camera %s in %ss...", self.camera_name, settings.RTSP_RECONNECT_DELAY)
                self._stop_event.wait(settings.RTSP_RECONNECT_DELAY)

    def _process_frame(self, frame: np.ndarray):
        """Detect faces in frame and record attendance."""
        try:
            detections = face_engine.extract_embedding_from_frame(frame)
        except Exception as e:
            logger.error("Face detection error on camera %s: %s", self.camera_name, e)
            return

        if not detections:
            return

        db = SessionLocal()
        try:
            for bbox, embedding in detections:
                self._match_and_record(db, embedding)
        finally:
            db.close()

    def _match_and_record(self, db, embedding: np.ndarray):
        """Match embedding against enrolled students using pgvector nearest neighbor."""
        embedding_list = embedding.tolist()
        result = db.execute(
            text(
                "SELECT id, student_id, name, 1 - (face_embedding <=> CAST(:query AS vector)) AS similarity "
                "FROM students "
                "WHERE is_active = true AND face_embedding IS NOT NULL "
                "ORDER BY face_embedding <=> CAST(:query AS vector) "
                "LIMIT 1"
            ),
            {"query": str(embedding_list)},
        ).fetchone()

        if result is None:
            return

        student_db_id, student_code, student_name, similarity = result

        if similarity < settings.FACE_RECOGNITION_TOLERANCE:
            return

        if self._is_on_cooldown(student_db_id):
            return

        now = datetime.now(timezone.utc)
        today = date.today()

        if self.direction == "entry":
            # Check-in: create a new attendance record if none exists today
            existing = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == student_db_id,
                    AttendanceRecord.date == today,
                )
                .first()
            )
            if existing is None:
                # Determine if late
                school_start = datetime.strptime(settings.SCHOOL_START_TIME, "%H:%M").time()
                late_threshold = (
                    datetime.combine(today, school_start) + timedelta(minutes=settings.LATE_THRESHOLD_MINUTES)
                ).time()
                current_time = now.time()
                status = AttendanceStatus.late if current_time > late_threshold else AttendanceStatus.present

                record = AttendanceRecord(
                    student_id=student_db_id,
                    check_in=now,
                    date=today,
                    status=status,
                    method=AttendanceMethod.rtsp_auto,
                    confidence=round(similarity, 4),
                    camera_name=self.camera_name,
                )
                db.add(record)
                db.commit()
                logger.info(
                    "RTSP check-in: %s (%s) via %s [confidence=%.3f, status=%s]",
                    student_name, student_code, self.camera_name, similarity, status.value,
                )

        elif self.direction == "exit":
            # Check-out: update the latest record for today
            existing = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == student_db_id,
                    AttendanceRecord.date == today,
                )
                .order_by(AttendanceRecord.created_at.desc())
                .first()
            )
            if existing and existing.check_out is None:
                existing.check_out = now
                db.commit()
                logger.info(
                    "RTSP check-out: %s (%s) via %s [confidence=%.3f]",
                    student_name, student_code, self.camera_name, similarity,
                )

        self._last_attendance[student_db_id] = now

        # Add to recent detections buffer
        detection = RecentDetection(
            student_name=student_name,
            student_id=student_code,
            camera_name=self.camera_name,
            confidence=similarity,
            timestamp=now,
        )
        rtsp_manager.add_detection(detection)


class RTSPManager:
    """Manages all camera workers."""

    def __init__(self):
        self._workers: dict[int, CameraWorker] = {}
        self._recent_detections: deque[RecentDetection] = deque(maxlen=200)
        self._lock = threading.Lock()

    def start_camera(self, camera_id: int, camera_name: str, rtsp_url: str, direction: str):
        with self._lock:
            if camera_id in self._workers:
                self._workers[camera_id].stop()
            worker = CameraWorker(camera_id, camera_name, rtsp_url, direction)
            self._workers[camera_id] = worker
            worker.start()

    def stop_camera(self, camera_id: int):
        with self._lock:
            worker = self._workers.pop(camera_id, None)
            if worker:
                worker.stop()

    def stop_all(self):
        with self._lock:
            for worker in self._workers.values():
                worker.stop()
            self._workers.clear()

    def is_running(self, camera_id: int) -> bool:
        with self._lock:
            worker = self._workers.get(camera_id)
            return worker is not None and worker._thread is not None and worker._thread.is_alive()

    def add_detection(self, detection: RecentDetection):
        self._recent_detections.append(detection)

    def get_recent_detections(self, minutes: int = 5) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return [
            d.to_dict()
            for d in self._recent_detections
            if d.timestamp > cutoff
        ]

    def start_active_cameras(self):
        """Start workers for all active cameras in the database."""
        db = SessionLocal()
        try:
            cameras = db.query(Camera).filter(Camera.is_active == True).all()
            for cam in cameras:
                self.start_camera(cam.id, cam.name, cam.rtsp_url, cam.direction.value)
            logger.info("Started %d active camera workers", len(cameras))
        finally:
            db.close()


# Global singleton
rtsp_manager = RTSPManager()
