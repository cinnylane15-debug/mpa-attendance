from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Class, User
from app.schemas import ClassCreate, ClassUpdate, ClassResponse

router = APIRouter(prefix="/api/classes", tags=["Classes"])


def _class_to_response(cls: Class) -> ClassResponse:
    return ClassResponse(
        id=cls.id,
        name=cls.name,
        section=cls.section,
        grade=cls.grade,
        teacher_id=cls.teacher_id,
        student_count=len(cls.students) if cls.students else 0,
        created_at=cls.created_at,
    )


@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(
    class_in: ClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new class (admin only)."""
    cls = Class(**class_in.model_dump())
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return _class_to_response(cls)


@router.get("/", response_model=list[ClassResponse])
def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all classes."""
    classes = db.query(Class).order_by(Class.name).all()
    return [_class_to_response(c) for c in classes]


@router.get("/{class_id}", response_model=ClassResponse)
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a class with student count."""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return _class_to_response(cls)


@router.put("/{class_id}", response_model=ClassResponse)
def update_class(
    class_id: int,
    class_in: ClassUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update a class (admin only)."""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    for key, value in class_in.model_dump(exclude_unset=True).items():
        setattr(cls, key, value)
    db.commit()
    db.refresh(cls)
    return _class_to_response(cls)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a class (admin only)."""
    cls = db.query(Class).filter(Class.id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    db.delete(cls)
    db.commit()
