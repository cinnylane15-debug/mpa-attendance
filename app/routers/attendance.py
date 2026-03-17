import json
import os
import uuid
import datetime
from typing import List, Optional

import face_recognition
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Employee, AttendanceRecord, AttendanceStatus, CheckMethod
from app.schemas import (
    AttendanceRecordOut,
    FaceCheckInResponse,
    CheckOutRequest,
    CheckOutResponse,
    LiveDetection,
)
from app.auth import get_current_user

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


def _record_to_out(record: AttendanceRecord) -> AttendanceRecordOut:
    return AttendanceRecordOut(
        id=record.id,
        employee_id=record.employee_id,
        employee_name=record.employee.name if record.employee else None,
        check_in=record.check_in,
        check_out=record.check_out,
        date=record.date,
        status=record.status,
        method=record.method,
        confidence=record.confidence,
        created_at=record.created_at,
    )


@router.post("/check-in", response_model=FaceCheckInResponse)
def face_check_in(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Check in via face recognition. Upload a photo and the system identifies the employee."""
    allowed = {"image/jpeg", "image/png", "image/jpg"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG images are accepted")

    contents = file.read()

    # Save temporarily
    tmp_filename = f"checkin_{uuid.uuid4().hex[:12]}.jpg"
    tmp_path = os.path.join(settings.UPLOAD_DIR, tmp_filename)
    with open(tmp_path, "wb") as f:
        f.write(contents)

    try:
        # Detect faces in uploaded image
        image = face_recognition.load_image_file(tmp_path)
        unknown_encodings = face_recognition.face_encodings(image)

        if len(unknown_encodings) == 0:
            return FaceCheckInResponse(success=False, message="No face detected in the image")

        unknown_encoding = unknown_encodings[0]

        # Load all active employees with face encodings
        employees = (
            db.query(Employee)
            .filter(Employee.is_active == True, Employee.face_encoding.isnot(None))
            .all()
        )

        if not employees:
            return FaceCheckInResponse(
                success=False, message="No registered employees with face encodings found"
            )

        known_encodings = []
        known_employees = []
        for emp in employees:
            enc = np.array(json.loads(emp.face_encoding))
            known_encodings.append(enc)
            known_employees.append(emp)

        # Compare faces
        distances = face_recognition.face_distance(known_encodings, unknown_encoding)
        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])
        confidence = round(1.0 - best_distance, 4)

        if best_distance > settings.FACE_RECOGNITION_TOLERANCE:
            return FaceCheckInResponse(
                success=False,
                message="Face not recognized. No matching employee found.",
                confidence=confidence,
            )

        matched_employee = known_employees[best_idx]
        today = datetime.date.today()

        # Check if already checked in today
        existing = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.employee_id == matched_employee.id,
                AttendanceRecord.date == today,
            )
            .first()
        )
        if existing:
            return FaceCheckInResponse(
                success=False,
                message=f"{matched_employee.name} has already checked in today",
                employee_name=matched_employee.name,
                employee_id=matched_employee.employee_id,
                confidence=confidence,
            )

        # Determine status based on check-in time (late if after 09:00)
        now = datetime.datetime.utcnow()
        status_val = AttendanceStatus.present
        if now.hour >= 9:
            status_val = AttendanceStatus.late

        record = AttendanceRecord(
            employee_id=matched_employee.id,
            check_in=now,
            date=today,
            status=status_val,
            method=CheckMethod.face_recognition,
            confidence=confidence,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return FaceCheckInResponse(
            success=True,
            message=f"Check-in successful for {matched_employee.name}",
            employee_name=matched_employee.name,
            employee_id=matched_employee.employee_id,
            confidence=confidence,
            attendance_id=record.id,
        )
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/check-out", response_model=CheckOutResponse)
def check_out(
    payload: CheckOutRequest,
    db: Session = Depends(get_db),
):
    """Check out an employee by their employee_id."""
    emp = db.query(Employee).filter(Employee.employee_id == payload.employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    today = datetime.date.today()
    record = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.employee_id == emp.id,
            AttendanceRecord.date == today,
        )
        .first()
    )

    if not record:
        return CheckOutResponse(
            success=False,
            message=f"{emp.name} has not checked in today",
            employee_name=emp.name,
        )
    if record.check_out is not None:
        return CheckOutResponse(
            success=False,
            message=f"{emp.name} has already checked out today",
            employee_name=emp.name,
            check_out=record.check_out,
        )

    now = datetime.datetime.utcnow()
    record.check_out = now

    # Mark half-day if worked less than 4 hours
    if record.check_in:
        duration = (now - record.check_in).total_seconds() / 3600
        if duration < 4:
            record.status = AttendanceStatus.half_day

    db.commit()
    db.refresh(record)

    return CheckOutResponse(
        success=True,
        message=f"Check-out successful for {emp.name}",
        employee_name=emp.name,
        check_out=record.check_out,
    )


@router.get("/records", response_model=List[AttendanceRecordOut])
def list_attendance_records(
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    employee_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get attendance records with optional filters."""
    query = db.query(AttendanceRecord).join(Employee)

    if start_date:
        query = query.filter(AttendanceRecord.date >= start_date)
    if end_date:
        query = query.filter(AttendanceRecord.date <= end_date)
    if employee_id:
        query = query.filter(Employee.employee_id == employee_id)
    if department:
        query = query.filter(Employee.department == department)

    records = (
        query.order_by(AttendanceRecord.date.desc(), AttendanceRecord.check_in.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_record_to_out(r) for r in records]


@router.get("/live", response_model=List[LiveDetection])
def live_detections(
    minutes: int = Query(5, ge=1, le=60),
    _current_user=Depends(get_current_user),
):
    """Return recent RTSP auto-detections from the last N minutes."""
    from app.rtsp_worker import get_recent_detections

    detections = get_recent_detections(minutes=minutes)
    return [
        LiveDetection(
            employee_name=d["employee_name"],
            employee_id=d["employee_id"],
            camera_name=d["camera_name"],
            camera_location=d["camera_location"],
            direction=d["direction"],
            confidence=d["confidence"],
            detected_at=d["detected_at"],
        )
        for d in detections
    ]


@router.get("/today", response_model=List[AttendanceRecordOut])
def today_attendance(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get all attendance records for today."""
    today = datetime.date.today()
    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == today)
        .order_by(AttendanceRecord.check_in.desc())
        .all()
    )
    return [_record_to_out(r) for r in records]
