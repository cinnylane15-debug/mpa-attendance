from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Schedule, Class, User
from app.schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse

router = APIRouter(prefix="/api/schedules", tags=["Schedules"])


def _schedule_to_response(sched: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=sched.id,
        class_id=sched.class_id,
        class_name=sched.schedule_class.name if sched.schedule_class else None,
        day_of_week=sched.day_of_week,
        start_time=sched.start_time,
        end_time=sched.end_time,
        is_active=sched.is_active,
    )


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    sched_in: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new schedule entry."""
    if not db.query(Class).filter(Class.id == sched_in.class_id).first():
        raise HTTPException(status_code=404, detail="Class not found")
    if sched_in.day_of_week < 0 or sched_in.day_of_week > 6:
        raise HTTPException(status_code=400, detail="day_of_week must be 0-6")

    schedule = Schedule(**sched_in.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return _schedule_to_response(schedule)


@router.get("/", response_model=list[ScheduleResponse])
def list_schedules(
    class_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List schedules, optionally filtered by class."""
    query = db.query(Schedule)
    if class_id is not None:
        query = query.filter(Schedule.class_id == class_id)
    schedules = query.order_by(Schedule.class_id, Schedule.day_of_week).all()
    return [_schedule_to_response(s) for s in schedules]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single schedule entry."""
    sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _schedule_to_response(sched)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    sched_in: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a schedule entry."""
    sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = sched_in.model_dump(exclude_unset=True)
    if "day_of_week" in update_data:
        if update_data["day_of_week"] < 0 or update_data["day_of_week"] > 6:
            raise HTTPException(status_code=400, detail="day_of_week must be 0-6")

    for key, value in update_data.items():
        setattr(sched, key, value)
    db.commit()
    db.refresh(sched)
    return _schedule_to_response(sched)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a schedule entry."""
    sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(sched)
    db.commit()
