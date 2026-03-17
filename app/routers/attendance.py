import json
import os
import uuid
import datetime
from typing import List, Optional

import face_recognition
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Employee, AttendanceRecord, User
from app.schemas import AttendanceOut, CheckInResponse, CheckOutResponse
from app.auth import get_current_user

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


def _build_attendance_out(record: AttendanceRecord) -> AttendanceOut:
    """Helper to build an AttendanceOut with employee info."""
    return AttendanceOut(
        id=record.id,
        employee_id=record.employee_id,
        employee_name=record.employee.name if record.employee else None,
        employee_code=record.employee.employee_id if record.employee else None,
        check_in=record.check_in,
        check_out=record.check_out,
        date=record.date,
        status=record.status,
        method=record.method,
        confidence=record.confidence,
        created_at=record.created_at,
    )


@router.post("/check-in", response_model=CheckInResponse)
def check_in_via_face(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Check in an employee using face recognition.

    Upload a photo; the system detects the face, compares it against all
    registered employee face encodings, and records attendance if a match
    is found.
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG and PNG images are accepted",
        )

    # Save the uploaded photo temporarily
    contents = file.read()
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    temp_filename = f"checkin_{uuid.uuid4().hex[:12]}.{ext}"
    temp_filepath = os.path.join(settings.UPLOAD_DIR, temp_filename)
    with open(temp_filepath, "wb") as f:
        f.write(contents)

    try:
        # Detect face in the uploaded photo
        image = face_recognition.load_image_file(temp_filepath)
        unknown_encodings = face_recognition.face_encodings(image)

        if len(unknown_encodings) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No face detected in the uploaded image.",
            )

        unknown_encoding = unknown_encodings[0]

        # Load all active employees with face encodings
        employees = (
            db.query(Employee)
            .filter(Employee.is_active.is_(True), Employee.face_encoding.isnot(None))
            .all()
        )

        if not employees:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No employees with registered faces found.",
            )

        # Compare against known encodings
        known_encodings = []
        known_employees = []
        for emp in employees:
            enc = np.array(json.loads(emp.face_encoding))
            known_encodings.append(enc)
            known_employees.append(emp)

        distances = face_recognition.face_distance(known_encodings, unknown_encoding)
        best_idx = int(np.argmin(distances))
        best_distance = float(distances[best_idx])

        if best_distance > settings.FACE_RECOGNITION_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No matching employee found. Best distance: {best_distance:.4f} (threshold: {settings.FACE_RECOGNITION_TOLERANCE})",
            )

        matched_employee = known_employees[best_idx]
        confidence = round(1.0 - best_distance, 4)
        today = datetime.date.today()
        now = datetime.datetime.now()

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
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee '{matched_employee.name}' has already checked in today.",
            )

        # Determine status (late if after 09:00)
        attendance_status = "present"
        if now.hour >= 9:
            attendance_status = "late"

        record = AttendanceRecord(
            employee_id=matched_employee.id,
            check_in=now,
            date=today,
            status=attendance_status,
            method="face_recognition",
            confidence=confidence,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return CheckInResponse(
            message=f"Check-in successful for {matched_employee.name}",
            employee_name=matched_employee.name,
            employee_id=matched_employee.employee_id,
            confidence=confidence,
            attendance_id=record.id,
        )
    finally:
        # Clean up temp file
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)


@router.post("/check-out/{employee_db_id}", response_model=CheckOutResponse)
def check_out(
    employee_db_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check out an employee for today."""
    employee = db.query(Employee).filter(Employee.id == employee_db_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    today = datetime.date.today()
    record = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.employee_id == employee.id,
            AttendanceRecord.date == today,
        )
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No check-in record found for today. Employee must check in first.",
        )
    if record.check_out is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee has already checked out today.",
        )

    now = datetime.datetime.now()
    record.check_out = now
    db.commit()
    db.refresh(record)

    return CheckOutResponse(
        message=f"Check-out successful for {employee.name}",
        employee_name=employee.name,
        employee_id=employee.employee_id,
        check_out=now,
    )


@router.get("/records", response_model=List[AttendanceOut])
def list_attendance_records(
    date: Optional[datetime.date] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    employee_id: Optional[int] = Query(None, description="Filter by employee database ID"),
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List attendance records with optional filters."""
    query = db.query(AttendanceRecord)

    if date:
        query = query.filter(AttendanceRecord.date == date)
    if employee_id:
        query = query.filter(AttendanceRecord.employee_id == employee_id)
    if start_date:
        query = query.filter(AttendanceRecord.date >= start_date)
    if end_date:
        query = query.filter(AttendanceRecord.date <= end_date)

    records = (
        query.order_by(AttendanceRecord.date.desc(), AttendanceRecord.check_in.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_build_attendance_out(r) for r in records]


@router.get("/report/daily", response_model=List[AttendanceOut])
def daily_report(
    date: datetime.date = Query(default=None, description="Date for report (defaults to today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a daily attendance report."""
    if date is None:
        date = datetime.date.today()

    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == date)
        .order_by(AttendanceRecord.check_in)
        .all()
    )
    return [_build_attendance_out(r) for r in records]
