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
from app.models import Student, StudentPhoto, User, Class, UnknownFace
from app.schemas import StudentCreate, StudentResponse, StudentUpdate, StudentPhotoResponse

router = APIRouter(prefix="/api/students", tags=["Students"])


def _relative_upload_path(full_path: str) -> str:
    """Convert a full server path to a path relative to the uploads root.

    e.g. /app/uploads/unknown_faces/foo.jpg -> unknown_faces/foo.jpg
         uploads/photos/bar.jpg -> photos/bar.jpg
         /app/uploads/photos/baz.jpg -> photos/baz.jpg
    """
    if not full_path:
        return full_path
    # Find 'uploads/' in the path and return everything after it
    idx = full_path.find("uploads/")
    if idx >= 0:
        return full_path[idx + len("uploads/"):]
    return os.path.basename(full_path)


def _student_to_response(student: Student) -> StudentResponse:
    # Return relative path from uploads root
    photo = student.photo_path
    if photo:
        photo = _relative_upload_path(photo)
    return StudentResponse(
        id=student.id,
        student_id=student.student_id,
        name=student.name,
        class_id=student.class_id,
        class_name=student.student_class.name if student.student_class else None,
        guardian_name=student.guardian_name,
        guardian_phone=student.guardian_phone,
        photo_path=photo,
        has_face_embedding=len(student.photos) > 0 or student.face_embedding is not None,
        photo_count=len(student.photos),
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
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List students with optional class and search filters."""
    query = db.query(Student)
    if class_id is not None:
        query = query.filter(Student.class_id == class_id)
    if is_active is not None:
        query = query.filter(Student.is_active == is_active)
    if search:
        query = query.filter(
            (Student.name.ilike(f"%{search}%")) | (Student.student_id.ilike(f"%{search}%"))
        )
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
    # Nullify unknown_faces references to avoid FK constraint errors
    db.query(UnknownFace).filter(
        UnknownFace.best_match_student_id == student.id
    ).update({UnknownFace.best_match_student_id: None})
    db.query(UnknownFace).filter(
        UnknownFace.assigned_student_id == student.id
    ).update({UnknownFace.assigned_student_id: None})
    # Delete all photo files
    for photo in student.photos:
        if os.path.exists(photo.photo_path):
            try:
                os.remove(photo.photo_path)
            except OSError:
                pass
    if student.photo_path and os.path.exists(student.photo_path):
        try:
            os.remove(student.photo_path)
        except OSError:
            pass
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

    embedding_list = embedding.tolist()

    # Add to student_photos table
    photo = StudentPhoto(
        student_id=student.id,
        photo_path=filepath,
        face_embedding=embedding_list,
    )
    db.add(photo)

    # Update student's primary display photo and embedding to the latest
    student.photo_path = filepath
    student.face_embedding = embedding_list
    db.commit()
    db.refresh(student)
    return _student_to_response(student)


@router.get("/{student_id}/photos", response_model=list[StudentPhotoResponse])
def list_photos(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all photos for a student."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return [
        StudentPhotoResponse(
            id=p.id,
            photo_path=_relative_upload_path(p.photo_path),
            created_at=p.created_at,
        )
        for p in student.photos
    ]


@router.delete("/{student_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    student_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific photo from a student."""
    photo = db.query(StudentPhoto).filter(
        StudentPhoto.id == photo_id,
        StudentPhoto.student_id == student_id,
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Delete file
    if os.path.exists(photo.photo_path):
        try:
            os.remove(photo.photo_path)
        except OSError:
            pass

    db.delete(photo)
    db.flush()

    # Update student's primary photo to the next available
    student = db.query(Student).filter(Student.id == student_id).first()
    remaining = db.query(StudentPhoto).filter(
        StudentPhoto.student_id == student_id
    ).order_by(StudentPhoto.created_at.desc()).first()

    if remaining:
        student.photo_path = remaining.photo_path
        student.face_embedding = remaining.face_embedding
    else:
        student.photo_path = None
        student.face_embedding = None

    db.commit()
