import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, AttendanceRecord
from app.schemas import DashboardStats, AttendanceRecordOut
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get dashboard statistics: totals, today's attendance, recent activity."""
    today = datetime.date.today()

    total_employees = db.query(Employee).count()
    active_employees = db.query(Employee).filter(Employee.is_active == True).count()

    today_records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == today)
        .all()
    )

    today_present = sum(1 for r in today_records if r.status in ("present", "late", "half_day"))
    today_late = sum(1 for r in today_records if r.status == "late")
    today_absent = active_employees - today_present

    # Recent activity: last 10 attendance records
    recent = (
        db.query(AttendanceRecord)
        .order_by(AttendanceRecord.created_at.desc())
        .limit(10)
        .all()
    )

    recent_out = []
    for r in recent:
        recent_out.append(
            AttendanceRecordOut(
                id=r.id,
                employee_id=r.employee_id,
                employee_name=r.employee.name if r.employee else None,
                check_in=r.check_in,
                check_out=r.check_out,
                date=r.date,
                status=r.status,
                method=r.method,
                confidence=r.confidence,
                created_at=r.created_at,
            )
        )

    return DashboardStats(
        total_employees=total_employees,
        active_employees=active_employees,
        today_present=today_present,
        today_absent=max(today_absent, 0),
        today_late=today_late,
        recent_activity=recent_out,
    )
