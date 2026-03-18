import logging
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone, date
from urllib.parse import urlparse, parse_qs

import cv2
import httpx
import numpy as np
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.face_engine import face_engine
from app.models import AttendanceRecord, AttendanceStatus, AttendanceMethod, Camera, DetectionLog, Student, StudentPhoto, UnknownFace

logger = logging.getLogger(__name__)


def derive_snapshot_url(rtsp_url: str) -> str | None:
    """Derive Dahua HTTP snapshot URL from an RTSP URL.

    Example:
        rtsp://admin:pass@192.168.1.9:554/cam/realmonitor?channel=3&subtype=0
        -> http://admin:pass@192.168.1.9/cgi-bin/snapshot.cgi?channel=3
    """
    try:
        parsed = urlparse(rtsp_url)
        host = parsed.hostname
        user = parsed.username or ""
        password = parsed.password or ""
        qs = parse_qs(parsed.query)
        channel = qs.get("channel", ["1"])[0]
        auth = f"{user}:{password}@" if user else ""
        return f"http://{auth}{host}/cgi-bin/snapshot.cgi?channel={channel}"
    except Exception:
        return None


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
    """Background worker that processes a camera via RTSP stream or HTTP snapshots."""

    def __init__(self, camera_id: int, camera_name: str, rtsp_url: str,
                 direction: str, capture_mode: str = "snapshot", snapshot_url: str | None = None):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.direction = direction
        self.capture_mode = capture_mode
        self.snapshot_url = snapshot_url or derive_snapshot_url(rtsp_url)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_attendance: dict[int, datetime] = {}
        self._last_auto_learn: dict[int, datetime] = {}  # track auto-learn cooldown per student

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("Worker for camera %s is already running", self.camera_name)
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"cam-{self.camera_name}")
        self._thread.start()
        logger.info("Started %s worker for camera: %s", self.capture_mode, self.camera_name)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
            logger.info("Stopped worker for camera: %s", self.camera_name)

    def _is_on_cooldown(self, student_db_id: int) -> bool:
        last = self._last_attendance.get(student_db_id)
        if last is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
        return elapsed < settings.RTSP_COOLDOWN_MINUTES

    def _run(self):
        if self.capture_mode == "snapshot":
            self._run_snapshot()
        else:
            self._run_rtsp()

    def _run_snapshot(self):
        """Grab HTTP snapshots on an interval and process them."""
        if not self.snapshot_url:
            logger.error("No snapshot URL for camera %s, falling back to RTSP", self.camera_name)
            self._run_rtsp()
            return

        # Parse auth from snapshot URL for digest auth
        parsed = urlparse(self.snapshot_url)
        username = parsed.username or ""
        password = parsed.password or ""
        # Build clean URL without auth in it (httpx handles auth separately)
        clean_url = self.snapshot_url.replace(f"{username}:{password}@", "")

        logger.info("Starting snapshot capture for camera %s: %s", self.camera_name, clean_url)

        while not self._stop_event.is_set():
            try:
                with httpx.Client(timeout=10, verify=False) as client:
                    auth = httpx.DigestAuth(username, password)
                    resp = client.get(clean_url, auth=auth)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        img_array = np.frombuffer(resp.content, dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        if frame is not None:
                            self._process_frame(frame)
                        else:
                            logger.warning("Failed to decode snapshot from camera %s", self.camera_name)
                    else:
                        logger.warning("Bad snapshot response from %s: status=%d, size=%d",
                                       self.camera_name, resp.status_code, len(resp.content))
            except Exception as e:
                logger.error("Snapshot error for camera %s: %s", self.camera_name, e)

            self._stop_event.wait(settings.RTSP_FRAME_INTERVAL)

    def _run_rtsp(self):
        """Original RTSP stream processing."""
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
                self._match_and_record(db, embedding, frame, bbox)
        finally:
            db.close()

    def _save_unknown_face(self, db, frame: np.ndarray, bbox, embedding: np.ndarray,
                          confidence: float = None, best_match_id: int = None):
        """Save an unidentified face crop to disk and database."""
        import os
        import uuid

        unknown_dir = os.path.join(settings.UPLOAD_DIR, "unknown_faces")
        os.makedirs(unknown_dir, exist_ok=True)

        # Crop face from frame
        x1, y1, x2, y2 = [int(c) for c in bbox[:4]]
        h, w = frame.shape[:2]
        # Add padding
        pad = 30
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size == 0:
            return

        filename = f"unknown_{uuid.uuid4().hex[:12]}.jpg"
        filepath = os.path.join(unknown_dir, filename)
        cv2.imwrite(filepath, face_crop)

        unknown = UnknownFace(
            face_image_path=filepath,
            face_embedding=embedding.tolist(),
            confidence=round(confidence, 4) if confidence else None,
            best_match_student_id=best_match_id,
            camera_name=self.camera_name,
        )
        db.add(unknown)
        db.commit()
        logger.info("Saved unknown face from camera %s (confidence=%.3f)",
                     self.camera_name, confidence or 0)

    def _save_detection_photo(self, frame: np.ndarray, bbox, student_code: str, suffix: str) -> str:
        """Save a snapshot of the detected face (wider crop) to disk. Returns the file path."""
        import os
        import uuid

        detection_dir = os.path.join(settings.UPLOAD_DIR, "detections")
        os.makedirs(detection_dir, exist_ok=True)

        # Save a generous crop around the face for context
        x1, y1, x2, y2 = [int(c) for c in bbox[:4]]
        h, w = frame.shape[:2]
        face_w, face_h = x2 - x1, y2 - y1
        pad = int(max(face_w, face_h) * 0.8)
        x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
        x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
        crop = frame[y1:y2, x1:x2]

        if crop.size == 0:
            crop = frame  # fallback to full frame

        filename = f"{student_code}_{suffix}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(detection_dir, filename)
        cv2.imwrite(filepath, crop)
        return filepath

    def _match_and_record(self, db, embedding: np.ndarray, frame: np.ndarray = None, bbox=None):
        """Match embedding against enrolled students using pgvector nearest neighbor.

        Logic:
        - First detection after DAY_START_HOUR (5 AM) = check-in with photo
        - Every subsequent detection updates check-out time + photo (last one wins)
        - Every detection creates a DetectionLog entry with photo
        """
        embedding_list = embedding.tolist()

        # Search student_photos table first (multiple embeddings per student)
        result = db.execute(
            text(
                "SELECT s.id, s.student_id, s.name, "
                "1 - (sp.face_embedding <=> CAST(:query AS vector)) AS similarity "
                "FROM student_photos sp "
                "JOIN students s ON s.id = sp.student_id "
                "WHERE s.is_active = true "
                "ORDER BY sp.face_embedding <=> CAST(:query AS vector) "
                "LIMIT 1"
            ),
            {"query": str(embedding_list)},
        ).fetchone()

        # Fallback to students table for legacy single-embedding students
        if result is None:
            result = db.execute(
                text(
                    "SELECT id, student_id, name, "
                    "1 - (face_embedding <=> CAST(:query AS vector)) AS similarity "
                    "FROM students "
                    "WHERE is_active = true AND face_embedding IS NOT NULL "
                    "ORDER BY face_embedding <=> CAST(:query AS vector) "
                    "LIMIT 1"
                ),
                {"query": str(embedding_list)},
            ).fetchone()

        if result is None:
            if frame is not None and bbox is not None:
                self._save_unknown_face(db, frame, bbox, embedding)
            return

        student_db_id, student_code, student_name, similarity = result

        if similarity < settings.FACE_RECOGNITION_TOLERANCE:
            if frame is not None and bbox is not None:
                self._save_unknown_face(db, frame, bbox, embedding, similarity, student_db_id)
            return

        if self._is_on_cooldown(student_db_id):
            return

        now = datetime.now(timezone.utc)
        today = date.today()

        # Find existing attendance record for today
        existing = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.student_id == student_db_id,
                AttendanceRecord.date == today,
            )
            .first()
        )

        # Save detection photo
        photo_path = None
        if frame is not None and bbox is not None:
            photo_path = self._save_detection_photo(frame, bbox, student_code, now.strftime("%H%M%S"))

        if existing is None:
            # FIRST detection today = CHECK-IN
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
                check_in_photo=photo_path,
            )
            db.add(record)
            db.flush()  # get the record.id

            # Save detection log
            if photo_path:
                log = DetectionLog(
                    attendance_record_id=record.id,
                    student_id=student_db_id,
                    photo_path=photo_path,
                    confidence=round(similarity, 4),
                    camera_name=self.camera_name,
                    detected_at=now,
                )
                db.add(log)

            db.commit()
            logger.info(
                "Check-in: %s (%s) via %s [confidence=%.3f, status=%s]",
                student_name, student_code, self.camera_name, similarity, status.value,
            )
        else:
            # SUBSEQUENT detection = update CHECK-OUT (last one wins)
            existing.check_out = now
            existing.check_out_photo = photo_path
            existing.check_out_confidence = round(similarity, 4)

            # Save detection log
            if photo_path:
                log = DetectionLog(
                    attendance_record_id=existing.id,
                    student_id=student_db_id,
                    photo_path=photo_path,
                    confidence=round(similarity, 4),
                    camera_name=self.camera_name,
                    detected_at=now,
                )
                db.add(log)

            db.commit()
            logger.info(
                "Check-out updated: %s (%s) via %s [confidence=%.3f]",
                student_name, student_code, self.camera_name, similarity,
            )

        self._last_attendance[student_db_id] = now

        # Auto-learn: save high-confidence detections as new photos
        if (settings.AUTO_LEARN_ENABLED
                and similarity >= settings.AUTO_LEARN_MIN_CONFIDENCE
                and frame is not None and bbox is not None):
            self._auto_learn(db, student_db_id, student_code, frame, bbox, embedding, similarity)

        detection = RecentDetection(
            student_name=student_name,
            student_id=student_code,
            camera_name=self.camera_name,
            confidence=similarity,
            timestamp=now,
        )
        rtsp_manager.add_detection(detection)


    def _auto_learn(self, db, student_db_id: int, student_code: str,
                     frame: np.ndarray, bbox: np.ndarray, embedding: np.ndarray, similarity: float):
        """Automatically save high-confidence face detections as new student photos."""
        try:
            # Check cooldown — only auto-learn once per student per cooldown period
            last = self._last_auto_learn.get(student_db_id)
            if last is not None:
                hours_elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                if hours_elapsed < settings.AUTO_LEARN_COOLDOWN_HOURS:
                    return

            # Check if student already has max photos
            photo_count = db.query(StudentPhoto).filter(
                StudentPhoto.student_id == student_db_id
            ).count()
            if photo_count >= settings.AUTO_LEARN_MAX_PHOTOS:
                return

            # Crop face from frame with padding
            import os
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = [int(c) for c in bbox]
            pad = int(max(x2 - x1, y2 - y1) * 0.3)
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(w, x2 + pad)
            y2 = min(h, y2 + pad)
            face_crop = frame[y1:y2, x1:x2]

            if face_crop.size == 0:
                return

            # Save cropped face
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            import uuid
            filename = f"{student_code}_auto_{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join(settings.UPLOAD_DIR, filename)
            cv2.imwrite(filepath, face_crop)

            # Add to student_photos
            photo = StudentPhoto(
                student_id=student_db_id,
                photo_path=filepath,
                face_embedding=embedding.tolist(),
            )
            db.add(photo)
            db.commit()

            self._last_auto_learn[student_db_id] = datetime.now(timezone.utc)
            logger.info(
                "Auto-learned face for %s [confidence=%.3f, total_photos=%d]",
                student_code, similarity, photo_count + 1,
            )
        except Exception as e:
            logger.error("Auto-learn error for student %s: %s", student_code, e)
            db.rollback()


class RTSPManager:
    """Manages all camera workers."""

    def __init__(self):
        self._workers: dict[int, CameraWorker] = {}
        self._recent_detections: deque[RecentDetection] = deque(maxlen=200)
        self._lock = threading.Lock()

    def start_camera(self, camera_id: int, camera_name: str, rtsp_url: str,
                     direction: str, capture_mode: str = "snapshot", snapshot_url: str | None = None):
        with self._lock:
            if camera_id in self._workers:
                self._workers[camera_id].stop()
            worker = CameraWorker(camera_id, camera_name, rtsp_url, direction, capture_mode, snapshot_url)
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
                self.start_camera(
                    cam.id, cam.name, cam.rtsp_url, cam.direction.value,
                    cam.capture_mode.value if cam.capture_mode else "snapshot",
                    cam.snapshot_url,
                )
            logger.info("Started %d active camera workers", len(cameras))
        finally:
            db.close()


# Global singleton
rtsp_manager = RTSPManager()
