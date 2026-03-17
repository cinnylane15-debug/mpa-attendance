from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Student, AttendanceRecord, AttendanceStatus, Class, User
from app.schemas import DashboardStats, WeeklySummary, ClassStats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get overall attendance statistics for today."""
    today = date.today()

    total_students = db.query(Student).filter(Student.is_active == True).count()

    present_today = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == today, AttendanceRecord.status == AttendanceStatus.present)
        .count()
    )
    late_today = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.date == today, AttendanceRecord.status == AttendanceStatus.late)
        .count()
    )

    checked_in_today = present_today + late_today
    absent_today = max(0, total_students - checked_in_today)
    attendance_rate = (checked_in_today / total_students * 100) if total_students > 0 else 0.0

    return DashboardStats(
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        late_today=late_today,
        attendance_rate=round(attendance_rate, 1),
    )


@router.get("/weekly", response_model=list[WeeklySummary])
def get_weekly_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get attendance summary for the last 7 days."""
    today = date.today()
    total_students = db.query(Student).filter(Student.is_active == True).count()
    results = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)

        present = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.date == day, AttendanceRecord.status == AttendanceStatus.present)
            .count()
        )
        late = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.date == day, AttendanceRecord.status == AttendanceStatus.late)
            .count()
        )
        absent = max(0, total_students - present - late)

        results.append(WeeklySummary(date=day, present=present, absent=absent, late=late))

    return results


@router.get("/class-stats", response_model=list[ClassStats])
def get_class_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get per-class attendance breakdown for today."""
    today = date.today()
    classes = db.query(Class).order_by(Class.name).all()
    results = []

    for cls in classes:
        total = db.query(Student).filter(Student.class_id == cls.id, Student.is_active == True).count()

        present = (
            db.query(AttendanceRecord)
            .join(Student)
            .filter(
                Student.class_id == cls.id,
                AttendanceRecord.date == today,
                AttendanceRecord.status == AttendanceStatus.present,
            )
            .count()
        )
        late = (
            db.query(AttendanceRecord)
            .join(Student)
            .filter(
                Student.class_id == cls.id,
                AttendanceRecord.date == today,
                AttendanceRecord.status == AttendanceStatus.late,
            )
            .count()
        )
        absent = max(0, total - present - late)
        rate = ((present + late) / total * 100) if total > 0 else 0.0

        results.append(ClassStats(
            class_id=cls.id,
            class_name=cls.name,
            total_students=total,
            present_today=present,
            absent_today=absent,
            late_today=late,
            attendance_rate=round(rate, 1),
        ))

    return results
