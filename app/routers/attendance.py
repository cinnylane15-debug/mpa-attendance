import io
import tempfile
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import (
    AttendanceRecord, AttendanceStatus, AttendanceMethod, Student, Class,
)
from app.rtsp_worker import rtsp_manager
from app.schemas import (
    AttendanceResponse, ManualCheckIn, ManualCheckOut, ExcelExportRequest,
)
from app.models import User

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


def _record_to_response(record: AttendanceRecord) -> AttendanceResponse:
    student = record.student
    return AttendanceResponse(
        id=record.id,
        student_id=record.student_id,
        student_name=student.name if student else None,
        student_code=student.student_id if student else None,
        class_name=student.student_class.name if student and student.student_class else None,
        check_in=record.check_in,
        check_out=record.check_out,
        date=record.date,
        status=record.status.value,
        method=record.method.value,
        confidence=record.confidence,
        camera_name=record.camera_name,
        created_at=record.created_at,
    )


@router.get("/today", response_model=list[AttendanceResponse])
def get_today_attendance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get today's attendance records with student names."""
    today = date.today()
    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == today)
        .order_by(AttendanceRecord.check_in.desc())
        .all()
    )
    return [_record_to_response(r) for r in records]


@router.get("/records", response_model=list[AttendanceResponse])
def get_records(
    record_date: Optional[date] = Query(None, alias="date"),
    class_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get filtered attendance records."""
    query = db.query(AttendanceRecord)

    if record_date:
        query = query.filter(AttendanceRecord.date == record_date)
    if student_id:
        query = query.filter(AttendanceRecord.student_id == student_id)
    if class_id:
        query = query.join(Student).filter(Student.class_id == class_id)

    records = query.order_by(AttendanceRecord.date.desc(), AttendanceRecord.check_in.desc()).all()
    return [_record_to_response(r) for r in records]


@router.post("/check-in", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def manual_check_in(
    data: ManualCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manual check-in by student_id code."""
    student = db.query(Student).filter(Student.student_id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    today = date.today()
    existing = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.student_id == student.id, AttendanceRecord.date == today)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Student already checked in today")

    now = datetime.now(timezone.utc)
    school_start = datetime.strptime(settings.SCHOOL_START_TIME, "%H:%M").time()
    late_threshold = (
        datetime.combine(today, school_start) + timedelta(minutes=settings.LATE_THRESHOLD_MINUTES)
    ).time()
    att_status = AttendanceStatus.late if now.time() > late_threshold else AttendanceStatus.present

    record = AttendanceRecord(
        student_id=student.id,
        check_in=now,
        date=today,
        status=att_status,
        method=AttendanceMethod.manual,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_to_response(record)


@router.post("/check-out", response_model=AttendanceResponse)
def manual_check_out(
    data: ManualCheckOut,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manual check-out by student_id code."""
    student = db.query(Student).filter(Student.student_id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    today = date.today()
    record = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.student_id == student.id,
            AttendanceRecord.date == today,
            AttendanceRecord.check_out.is_(None),
        )
        .order_by(AttendanceRecord.created_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="No open check-in found for today")

    record.check_out = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _record_to_response(record)


@router.get("/live")
def get_live_detections(current_user: User = Depends(get_current_user)):
    """Get recent RTSP face detections from the last 5 minutes."""
    detections = rtsp_manager.get_recent_detections(minutes=5)
    return detections


@router.get("/export")
def export_attendance(
    start_date: str = Query(...),
    end_date: str = Query(...),
    class_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export attendance records to Excel file."""
    query = (
        db.query(AttendanceRecord)
        .join(Student)
        .filter(
            AttendanceRecord.date >= start_date,
            AttendanceRecord.date <= end_date,
        )
    )
    if class_id:
        query = query.filter(Student.class_id == class_id)

    records = query.order_by(AttendanceRecord.date, Student.student_id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Report"

    # Header row
    headers = ["Student ID", "Name", "Class", "Date", "Check In", "Check Out", "Status", "Method"]
    ws.append(headers)

    # Style header
    from openpyxl.styles import Font
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Data rows
    for record in records:
        student = record.student
        ws.append([
            student.student_id if student else "",
            student.name if student else "",
            student.student_class.name if student and student.student_class else "",
            record.date.isoformat(),
            record.check_in.strftime("%H:%M:%S") if record.check_in else "",
            record.check_out.strftime("%H:%M:%S") if record.check_out else "",
            record.status.value,
            record.method.value,
        ])

    # Auto-adjust column widths
    for col in ws.columns:
        max_length = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 30)

    # Write to bytes buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"attendance_{data.start_date}_{data.end_date}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
