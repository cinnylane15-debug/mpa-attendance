import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.face_engine import face_engine
from app.models import Student, User, Class
from app.schemas import StudentCreate, StudentResponse, StudentUpdate

router = APIRouter(prefix="/api/students", tags=["Students"])


def _student_to_response(student: Student) -> StudentResponse:
    return StudentResponse(
        id=student.id,
        student_id=student.student_id,
        name=student.name,
        class_id=student.class_id,
        class_name=student.student_class.name if student.student_class else None,
        guardian_name=student.guardian_name,
        guardian_phone=student.guardian_phone,
        photo_path=student.photo_path,
        has_face_embedding=student.face_embedding is not None,
        is_active=student.is_active,
        created_at=student.created_at,
    )


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    student_in: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new student."""
    if db.query(Student).filter(Student.student_id == student_in.student_id).first():
        raise HTTPException(status_code=400, detail="Student ID already exists")
    if student_in.class_id:
        if not db.query(Class).filter(Class.id == student_in.class_id).first():
            raise HTTPException(status_code=404, detail="Class not found")

    student = Student(**student_in.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return _student_to_response(student)


@router.get("/", response_model=list[StudentResponse])
def list_students(
    class_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List students with optional class filter."""
    query = db.query(Student)
    if class_id is not None:
        query = query.filter(Student.class_id == class_id)
    if is_active is not None:
        query = query.filter(Student.is_active == is_active)
    students = query.order_by(Student.name).all()
    return [_student_to_response(s) for s in students]


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single student by database ID."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return _student_to_response(student)


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    student_in: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a student."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_data = student_in.model_dump(exclude_unset=True)
    if "class_id" in update_data and update_data["class_id"] is not None:
        if not db.query(Class).filter(Class.id == update_data["class_id"]).first():
            raise HTTPException(status_code=404, detail="Class not found")

    for key, value in update_data.items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return _student_to_response(student)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a student."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(student)
    db.commit()


@router.post("/{student_id}/photo", response_model=StudentResponse)
def upload_photo(
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a student face photo and extract the face embedding."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/jpg"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG images are allowed")

    # Save file
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{student.student_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Extract face embedding
    try:
        embedding = face_engine.extract_embedding(filepath)
    except Exception as e:
        os.remove(filepath)
        raise HTTPException(status_code=500, detail=f"Face engine error: {str(e)}")

    if embedding is None:
        os.remove(filepath)
        raise HTTPException(status_code=400, detail="No face detected in the uploaded image")

    # Remove old photo if exists
    if student.photo_path and os.path.exists(student.photo_path):
        try:
            os.remove(student.photo_path)
        except OSError:
            pass

    student.photo_path = filepath
    student.face_embedding = embedding.tolist()
    db.commit()
    db.refresh(student)
    return _student_to_response(student)
