from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Holiday, User
from app.schemas import HolidayCreate, HolidayUpdate, HolidayResponse

router = APIRouter(prefix="/api/holidays", tags=["Holidays"])


@router.post("/", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(
    hol_in: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new holiday."""
    existing = db.query(Holiday).filter(Holiday.date == hol_in.date).first()
    if existing:
        raise HTTPException(status_code=400, detail="A holiday already exists on this date")

    holiday = Holiday(**hol_in.model_dump())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.get("/", response_model=list[HolidayResponse])
def list_holidays(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all holidays ordered by date."""
    holidays = db.query(Holiday).order_by(Holiday.date).all()
    return holidays


@router.get("/upcoming", response_model=list[HolidayResponse])
def upcoming_holidays(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the next 5 upcoming holidays."""
    today = date.today()
    holidays = (
        db.query(Holiday)
        .filter(Holiday.date >= today)
        .order_by(Holiday.date)
        .limit(5)
        .all()
    )
    return holidays


@router.get("/{holiday_id}", response_model=HolidayResponse)
def get_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single holiday."""
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return holiday


@router.put("/{holiday_id}", response_model=HolidayResponse)
def update_holiday(
    holiday_id: int,
    hol_in: HolidayUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a holiday."""
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")

    update_data = hol_in.model_dump(exclude_unset=True)
    if "date" in update_data:
        conflict = db.query(Holiday).filter(
            Holiday.date == update_data["date"], Holiday.id != holiday_id
        ).first()
        if conflict:
            raise HTTPException(status_code=400, detail="A holiday already exists on this date")

    for key, value in update_data.items():
        setattr(holiday, key, value)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a holiday."""
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(holiday)
    db.commit()
