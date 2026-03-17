import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, AttendanceRecord, User
from app.schemas import DashboardStats, AttendanceOut
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard statistics for today."""
    today = datetime.date.today()

    total_employees = db.query(Employee).count()
    active_employees = db.query(Employee).filter(Employee.is_active.is_(True)).count()

    today_records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == today)
        .all()
    )

    today_present = len(today_records)
    today_absent = active_employees - today_present
    if today_absent < 0:
        today_absent = 0
    today_checked_out = sum(1 for r in today_records if r.check_out is not None)

    # Recent activity: last 10 attendance records
    recent = (
        db.query(AttendanceRecord)
        .order_by(AttendanceRecord.created_at.desc())
        .limit(10)
        .all()
    )

    recent_activity: List[AttendanceOut] = []
    for record in recent:
        recent_activity.append(
            AttendanceOut(
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
        )

    return DashboardStats(
        total_employees=total_employees,
        active_employees=active_employees,
        today_present=today_present,
        today_absent=today_absent,
        today_checked_out=today_checked_out,
        recent_activity=recent_activity,
    )
