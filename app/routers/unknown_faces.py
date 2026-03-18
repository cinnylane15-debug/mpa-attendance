import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import UnknownFace, Student, User
from app.schemas import UnknownFaceResponse, AssignUnknownFace

router = APIRouter(prefix="/api/unknown-faces", tags=["Unknown Faces"])


def _face_to_response(face: UnknownFace) -> UnknownFaceResponse:
    return UnknownFaceResponse(
        id=face.id,
        face_image_path=os.path.basename(face.face_image_path) if face.face_image_path else "",
        confidence=face.confidence,
        best_match_student_id=face.best_match_student_id,
        best_match_name=face.best_match.name if face.best_match else None,
        camera_name=face.camera_name,
        assigned_student_id=face.assigned_student_id,
        assigned_student_name=face.assigned_student.name if face.assigned_student else None,
        is_resolved=face.is_resolved,
        captured_at=face.captured_at,
    )


@router.get("/", response_model=list[UnknownFaceResponse])
def list_unknown_faces(
    resolved: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List unknown/unidentified faces, newest first."""
    query = db.query(UnknownFace)
    if resolved is not None:
        query = query.filter(UnknownFace.is_resolved == resolved)
    faces = query.order_by(UnknownFace.captured_at.desc()).limit(limit).all()
    return [_face_to_response(f) for f in faces]


@router.get("/stats")
def unknown_faces_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get counts of unresolved and total unknown faces."""
    total = db.query(UnknownFace).count()
    unresolved = db.query(UnknownFace).filter(UnknownFace.is_resolved == False).count()
    return {"total": total, "unresolved": unresolved}


@router.post("/{face_id}/assign", response_model=UnknownFaceResponse)
def assign_to_student(
    face_id: int,
    data: AssignUnknownFace,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Assign an unknown face to a student."""
    face = db.query(UnknownFace).filter(UnknownFace.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Unknown face not found")

    student = db.query(Student).filter(Student.id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    face.assigned_student_id = data.student_id
    face.is_resolved = True
    face.resolved_at = datetime.now(timezone.utc)

    # If student has no face embedding yet, use this one
    if student.face_embedding is None and face.face_embedding is not None:
        student.face_embedding = face.face_embedding
        student.photo_path = face.face_image_path

    db.commit()
    db.refresh(face)
    return _face_to_response(face)


@router.post("/{face_id}/dismiss")
def dismiss_face(
    face_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Dismiss an unknown face (mark as resolved without assigning)."""
    face = db.query(UnknownFace).filter(UnknownFace.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Unknown face not found")

    face.is_resolved = True
    face.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Face dismissed"}


@router.delete("/{face_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unknown_face(
    face_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete an unknown face record and its image."""
    face = db.query(UnknownFace).filter(UnknownFace.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Unknown face not found")

    # Delete image file
    if face.face_image_path and os.path.exists(face.face_image_path):
        try:
            os.remove(face.face_image_path)
        except OSError:
            pass

    db.delete(face)
    db.commit()
